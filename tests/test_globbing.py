"""Tests for the gitignore-flavoured glob matcher."""

from __future__ import annotations

import pytest

from agentfence.adapters.globbing import glob_match, normalize_path, path_rule_matches


@pytest.mark.parametrize(
    ("pattern", "text", "expected"),
    [
        ("*.env", ".env", True),  # * matches zero chars, like gitignore
        ("*.env", "prod.env", True),
        ("*.env", "conf/prod.env", False),  # * stops at separator
        ("*", "file", True),
        ("*", "a/b", False),  # single star stops at separator
        ("**", "a/b/c", True),  # double star crosses separators
        ("src/**", "src/app.py", True),
        ("src/**", "src/nested/deep.py", True),
        ("src/**", "lib/app.py", False),
        ("**/x", "x", True),
        ("**/x", "a/b/x", True),
        ("a?c", "abc", True),
        ("a?c", "a/c", False),
    ],
)
def test_glob_match(pattern: str, text: str, expected: bool) -> None:
    assert glob_match(pattern, text) is expected


def test_normalize_strips_leading_dot_slash_but_keeps_dotdot() -> None:
    assert normalize_path("./.env") == ".env"
    assert normalize_path("./a/../b") == "a/../b"  # traversal preserved
    assert normalize_path("secrets/") == "secrets"


def test_path_rule_directory_prefix_semantics() -> None:
    assert path_rule_matches("secrets", "secrets/key.pem")
    assert path_rule_matches("./.env", "./.env")
    # a traversal spelling slips past a literal path rule (a real bypass)
    assert not path_rule_matches("./.env", "./x/../.env")
