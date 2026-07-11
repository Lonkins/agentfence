"""Exceptions raised by the sandbox runner."""

from __future__ import annotations


class SandboxError(RuntimeError):
    """Base class for all sandbox failures."""


class SandboxUnavailableError(SandboxError):
    """Docker is not installed, or the daemon is not reachable.

    Raised when the runner cannot even begin — the deterministic core never
    triggers this because it never touches the sandbox.
    """


class SandboxSecurityError(SandboxError):
    """The runner could not apply a required isolation control, so it refused.

    The sandbox fails closed: if network, filesystem, or privilege controls
    cannot be guaranteed, no untrusted command is executed.
    """
