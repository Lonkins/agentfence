"""Configuration and result models for the sandbox runner.

These are the validated boundary between agentfence and Docker. Defaults are
deliberately locked down: no network, non-root, read-only root filesystem,
tight resource caps. Loosening any of them is an explicit, visible choice.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

# Default sandbox image. Alpine is tiny, has busybox `timeout`/`sleep`, and
# needs no build step. Live mode (opt-in) can point at a purpose-built image.
DEFAULT_IMAGE = "alpine:3.20"

# Keep-alive sleep for the session container, in seconds. Bounded so a leaked
# container self-terminates instead of lingering. ponytail: fixed ceiling; a
# single run never approaches an hour of wall clock.
_SESSION_KEEPALIVE_S = 3600


class SandboxConfig(BaseModel):
    """Immutable, validated sandbox parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    image: str = DEFAULT_IMAGE
    # Network is OFF by default. Egress scenarios assert the attempt is blocked,
    # not that traffic succeeds — so they never need this enabled.
    network_enabled: bool = False
    memory_mb: int = Field(default=256, ge=16, le=8192)
    cpus: float = Field(default=1.0, gt=0.0, le=8.0)
    pids_limit: int = Field(default=128, ge=1, le=4096)
    timeout_s: int = Field(default=30, ge=1, le=600)
    workspace_mb: int = Field(default=64, ge=1, le=2048)
    workdir: str = "/workspace"
    # Non-root by default: "uid:gid". root (0:0) is rejected below.
    user: str = "1000:1000"
    read_only_root: bool = True
    drop_all_capabilities: bool = True
    extra_env: Mapping[str, str] = Field(default_factory=dict)

    @property
    def keepalive_command(self) -> list[str]:
        """PID 1 for the session container: sleep, then exit on its own."""
        return ["sleep", str(_SESSION_KEEPALIVE_S)]

    def is_hardened(self) -> tuple[bool, str]:
        """Report whether isolation controls are intact; used to fail closed.

        Returns ``(ok, reason)``. ``reason`` is empty when ``ok`` is True.
        """
        if self.user.split(":", 1)[0] in {"0", "root"}:
            return False, "sandbox refuses to run as root (set a non-zero uid)"
        if not self.read_only_root:
            return False, "read-only root filesystem is disabled"
        if not self.drop_all_capabilities:
            return False, "Linux capabilities are not dropped"
        return True, ""


class SandboxResult(BaseModel):
    """Outcome of a single command executed inside the sandbox."""

    model_config = ConfigDict(frozen=True)

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float

    @property
    def ok(self) -> bool:
        """True when the command completed successfully and was not killed."""
        return self.exit_code == 0 and not self.timed_out
