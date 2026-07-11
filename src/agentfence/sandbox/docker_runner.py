"""Rootless, networkless, ephemeral Docker execution.

The runner creates one container per session with a locked-down profile
(ADR-0003), executes commands inside it, and removes it on exit. Nothing
persists; the host filesystem and network are unreachable from scenario code
under normal container isolation.

Docker is an *optional* dependency. Importing this module never requires it;
only constructing a :class:`DockerSandbox` does.
"""

from __future__ import annotations

import base64
import contextlib
import shlex
import time
from collections.abc import Sequence
from posixpath import dirname
from types import TracebackType
from typing import Any

from agentfence.sandbox.config import SandboxConfig, SandboxResult
from agentfence.sandbox.errors import (
    SandboxError,
    SandboxSecurityError,
    SandboxUnavailableError,
)

try:  # Docker SDK is only needed at runtime for actual execution.
    import docker as _docker
    from docker.errors import DockerException, ImageNotFound, NotFound

    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - exercised only without extras
    _docker = None
    DockerException = Exception
    ImageNotFound = Exception
    NotFound = Exception
    _IMPORT_ERROR = exc

_LABEL = "io.agentfence.sandbox"


def docker_available() -> bool:
    """Return True if the Docker SDK is installed and the daemon responds."""
    if _docker is None:
        return False
    client: Any = None
    try:
        client = _docker.from_env()
        client.ping()
        return True
    except Exception:
        return False
    finally:
        if client is not None:
            with contextlib.suppress(Exception):  # best-effort cleanup
                client.close()


def _decode(chunk: bytes | None) -> str:
    return chunk.decode("utf-8", errors="replace") if chunk else ""


class DockerSandbox:
    """A session-scoped, isolated execution environment.

    Use as a context manager::

        with DockerSandbox(SandboxConfig()) as box:
            box.put_file("/workspace/config.json", data)
            result = box.run("cat /workspace/config.json")

    The container is created on ``__enter__`` and force-removed on ``__exit__``.
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()
        self._client: Any = None
        self._container: Any = None

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> DockerSandbox:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def start(self) -> None:
        """Create and start the session container, failing closed on any gap."""
        ok, reason = self.config.is_hardened()
        if not ok:
            raise SandboxSecurityError(reason)

        if _docker is None:
            raise SandboxUnavailableError(
                "The Docker SDK is not installed. Install the sandbox extra: "
                "`pip install 'agentfence[sandbox]'`."
            ) from _IMPORT_ERROR

        try:
            self._client = _docker.from_env()
            self._client.ping()
        except DockerException as err:
            raise SandboxUnavailableError(
                "Cannot reach the Docker daemon. Is Docker running?"
            ) from err

        self._ensure_image()
        self._container = self._create_container()
        try:
            self._container.start()
        except DockerException as err:
            self.close()
            raise SandboxError(f"Failed to start sandbox container: {err}") from err

    def close(self) -> None:
        """Force-remove the container and close the client (idempotent)."""
        if self._container is not None:
            with contextlib.suppress(NotFound, DockerException):  # best-effort cleanup
                self._container.remove(force=True)
            self._container = None
        if self._client is not None:
            with contextlib.suppress(Exception):  # best-effort cleanup
                self._client.close()
            self._client = None

    # -- execution ---------------------------------------------------------

    def run(
        self,
        command: str | Sequence[str],
        *,
        timeout_s: int | None = None,
    ) -> SandboxResult:
        """Execute a command inside the sandbox and capture its result.

        A string is run through ``/bin/sh -c`` so shell features (command
        substitution, aliasing, chained commands) behave as they would for the
        real agent — that is exactly what the bypass scenarios need to probe.
        A sequence is executed as a bare argv with no shell.

        The command is wrapped with busybox ``timeout`` so it cannot hang the
        run. ponytail: per-command wall-clock ceiling via ``timeout``; the
        container's pids/memory caps bound everything else.
        """
        if self._container is None:
            raise SandboxError("Sandbox is not started; use it as a context manager.")

        limit = timeout_s if timeout_s is not None else self.config.timeout_s
        argv = self._build_argv(command, limit)

        started = time.monotonic()
        try:
            exit_code, output = self._container.exec_run(
                cmd=argv,
                demux=True,
                workdir=self.config.workdir,
                user=self.config.user,
                environment=dict(self.config.extra_env),
            )
        except DockerException as err:
            raise SandboxError(f"Command execution failed: {err}") from err
        duration = time.monotonic() - started

        stdout_b, stderr_b = output if output is not None else (None, None)
        code = int(exit_code) if exit_code is not None else -1
        # busybox `timeout` returns 143 (SIGTERM) / -k escalates to 137 (SIGKILL);
        # GNU coreutils returns 124. Combine exit code with wall clock.
        timed_out = code in {124, 137, 143} and duration >= limit * 0.9
        return SandboxResult(
            exit_code=code,
            stdout=_decode(stdout_b),
            stderr=_decode(stderr_b),
            timed_out=timed_out,
            duration_s=round(duration, 4),
        )

    def _build_argv(self, command: str | Sequence[str], limit: int) -> list[str]:
        prefix = ["timeout", "-s", "KILL", str(limit)]
        if isinstance(command, str):
            return [*prefix, "/bin/sh", "-c", command]
        return [*prefix, *command]

    # -- file transfer -----------------------------------------------------

    def put_file(self, path: str, content: str | bytes, *, mode: int = 0o600) -> None:
        """Write a file into the sandbox (must live under the writable workdir).

        Docker forbids ``put_archive`` into a read-only-rootfs container even for
        tmpfs mounts, so the file is materialised by exec'ing base64 decode into
        the writable workspace. Sized for config files (KB); ponytail: single
        argv carries the payload, fine below ARG_MAX.
        """
        if self._container is None:
            raise SandboxError("Sandbox is not started.")
        data = content.encode("utf-8") if isinstance(content, str) else content
        encoded = base64.b64encode(data).decode("ascii")
        quoted_path = shlex.quote(path)
        parent = shlex.quote(dirname(path) or "/")
        script = (
            f"mkdir -p {parent} && "
            f"printf %s {shlex.quote(encoded)} | base64 -d > {quoted_path} && "
            f"chmod {mode:o} {quoted_path}"
        )
        result = self.run(script)
        if not result.ok:
            raise SandboxError(
                f"Could not write {path} into the sandbox (is it under "
                f"{self.config.workdir}?): {result.stderr.strip() or result.exit_code}"
            )

    def read_file(self, path: str) -> bytes:
        """Read a file back out of the sandbox.

        Uses exec + base64 rather than ``get_archive`` because Docker's copy API
        cannot read from tmpfs mounts, which is exactly where the workspace lives.
        """
        if self._container is None:
            raise SandboxError("Sandbox is not started.")
        result = self.run(f"base64 {shlex.quote(path)}")
        if not result.ok:
            raise SandboxError(
                f"Could not read {path} from sandbox: {result.stderr.strip() or result.exit_code}"
            )
        # busybox base64 wraps output; b64decode discards the newlines.
        return base64.b64decode(result.stdout)

    # -- internals ---------------------------------------------------------

    def _ensure_image(self) -> None:
        try:
            self._client.images.get(self.config.image)
        except ImageNotFound:
            try:
                self._client.images.pull(self.config.image)
            except DockerException as err:
                raise SandboxError(
                    f"Could not pull sandbox image {self.config.image!r}: {err}"
                ) from err

    def _create_container(self) -> Any:
        cfg = self.config
        network_mode = "bridge" if cfg.network_enabled else "none"
        tmpfs = {
            cfg.workdir: f"size={cfg.workspace_mb}m,mode=1777",
            # In-container mount path, not a host temp file — writable /tmp on a
            # read-only root lets tools that need scratch space work.
            "/tmp": f"size={cfg.workspace_mb}m,mode=1777",  # noqa: S108
        }
        try:
            return self._client.containers.create(
                image=cfg.image,
                command=cfg.keepalive_command,
                detach=True,
                network_mode=network_mode,
                mem_limit=f"{cfg.memory_mb}m",
                nano_cpus=int(cfg.cpus * 1_000_000_000),
                pids_limit=cfg.pids_limit,
                read_only=cfg.read_only_root,
                user=cfg.user,
                cap_drop=["ALL"] if cfg.drop_all_capabilities else [],
                security_opt=["no-new-privileges"],
                tmpfs=tmpfs,
                working_dir=cfg.workdir,
                environment=dict(cfg.extra_env),
                labels={_LABEL: "1"},
            )
        except DockerException as err:
            raise SandboxError(f"Could not create sandbox container: {err}") from err


def run_once(command: str | Sequence[str], config: SandboxConfig | None = None) -> SandboxResult:
    """Convenience: spin up a sandbox, run one command, tear it down."""
    with DockerSandbox(config) as box:
        return box.run(command)
