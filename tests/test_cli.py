"""Smoke tests for the CLI entry point and packaging metadata."""

from __future__ import annotations

from typer.testing import CliRunner

from agentfence import __version__
from agentfence.cli import app

runner = CliRunner()


def test_version_flag_reports_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_command_reports_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # no_args_is_help exits with code 0 and prints usage.
    assert "Usage" in result.stdout
    assert "conformance" in result.stdout.lower()
