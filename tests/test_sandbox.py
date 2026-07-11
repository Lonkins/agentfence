"""Sandbox runner tests.

Unit tests run anywhere. Isolation tests are marked ``docker`` and skipped when
no daemon is reachable; CI runs them on a runner that has Docker.
"""

from __future__ import annotations

import docker
import pytest
from pydantic import ValidationError

from agentfence.sandbox import (
    DockerSandbox,
    SandboxConfig,
    SandboxSecurityError,
    docker_available,
)
from agentfence.sandbox.docker_runner import _decode

DOCKER_UP = docker_available()
requires_docker = pytest.mark.skipif(not DOCKER_UP, reason="Docker daemon not available")


# --------------------------------------------------------------------------- #
# Unit tests (no daemon required)
# --------------------------------------------------------------------------- #


def test_docker_available_returns_bool() -> None:
    assert isinstance(docker_available(), bool)


def test_decode_handles_none_and_bytes() -> None:
    assert _decode(None) == ""
    assert _decode(b"hello") == "hello"
    assert _decode(b"\xff\xfe") == "��"  # invalid utf-8 is replaced


def test_config_defaults_are_hardened() -> None:
    ok, reason = SandboxConfig().is_hardened()
    assert ok is True
    assert reason == ""


def test_config_rejects_out_of_range_values() -> None:
    with pytest.raises(ValidationError):
        SandboxConfig(memory_mb=1)  # below floor of 16
    with pytest.raises(ValidationError):
        SandboxConfig(cpus=0.0)  # must be > 0
    with pytest.raises(ValidationError):
        SandboxConfig(timeout_s=0)


def test_config_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SandboxConfig(privileged=True)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("user", "read_only", "drop_caps"),
    [
        ("0:0", True, True),
        ("root", True, True),
        ("1000:1000", False, True),
        ("1000:1000", True, False),
    ],
)
def test_unhardened_config_reports_reason(user: str, read_only: bool, drop_caps: bool) -> None:
    cfg = SandboxConfig(user=user, read_only_root=read_only, drop_all_capabilities=drop_caps)
    ok, reason = cfg.is_hardened()
    assert ok is False
    assert reason


def test_start_refuses_unhardened_config_before_touching_docker() -> None:
    box = DockerSandbox(SandboxConfig(user="0:0"))
    with pytest.raises(SandboxSecurityError):
        box.start()


def test_build_argv_wraps_shell_and_argv() -> None:
    box = DockerSandbox()
    assert box._build_argv("echo hi", 5) == [
        "timeout",
        "-s",
        "KILL",
        "5",
        "/bin/sh",
        "-c",
        "echo hi",
    ]
    assert box._build_argv(["ls", "-la"], 3) == ["timeout", "-s", "KILL", "3", "ls", "-la"]


def test_run_without_start_raises() -> None:
    box = DockerSandbox()
    with pytest.raises(Exception, match="not started"):
        box.run("echo hi")


# --------------------------------------------------------------------------- #
# Isolation tests (require Docker)
# --------------------------------------------------------------------------- #


@pytest.mark.docker
@requires_docker
def test_runs_command_and_captures_stdout() -> None:
    with DockerSandbox() as box:
        result = box.run("echo agentfence")
    assert result.ok
    assert result.exit_code == 0
    assert "agentfence" in result.stdout
    assert result.stderr == ""


@pytest.mark.docker
@requires_docker
def test_runs_as_non_root_user() -> None:
    with DockerSandbox() as box:
        result = box.run("id -u")
    assert "1000" in result.stdout


@pytest.mark.docker
@requires_docker
def test_root_filesystem_is_read_only() -> None:
    with DockerSandbox() as box:
        blocked = box.run("touch /etc/agentfence_probe")
        allowed = box.run("touch /workspace/ok && echo wrote")
    assert not blocked.ok, "writing outside the workspace should fail"
    assert allowed.ok, "writing inside the workspace should succeed"
    assert "wrote" in allowed.stdout


@pytest.mark.docker
@requires_docker
def test_network_egress_is_blocked() -> None:
    with DockerSandbox() as box:
        result = box.run("wget -q -T 3 -O /dev/null http://example.com")
    assert not result.ok, "network egress should be impossible with network disabled"


@pytest.mark.docker
@requires_docker
def test_command_timeout_is_enforced() -> None:
    with DockerSandbox() as box:
        result = box.run("sleep 10", timeout_s=1)
    assert result.timed_out
    assert not result.ok
    assert result.duration_s < 5


@pytest.mark.docker
@requires_docker
def test_put_and_read_file_roundtrip() -> None:
    with DockerSandbox() as box:
        box.put_file("/workspace/config.json", '{"k": "v"}')
        echoed = box.run("cat /workspace/config.json")
        raw = box.read_file("/workspace/config.json")
    assert '{"k": "v"}' in echoed.stdout
    assert raw == b'{"k": "v"}'


@pytest.mark.docker
@requires_docker
def test_container_is_removed_after_context() -> None:
    with DockerSandbox() as box:
        container_id = box._container.id
    client = docker.from_env()
    try:
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(container_id)
    finally:
        client.close()
