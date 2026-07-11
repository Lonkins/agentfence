"""A small gitignore-flavoured glob matcher used by path-based rule matching.

Supports ``*`` (any run of non-separator chars), ``**`` (any run including
separators), and ``?``. Deliberately does *not* resolve ``..`` or symlinks:
faithfully reproducing an agent matcher that operates on the literal path string
is what lets path-traversal bypasses surface as leaks (ADR-0002).
"""

from __future__ import annotations

import re
from functools import lru_cache

_SEP = "/"


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    parts: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        char = pattern[i]
        if char == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                parts.append(".*")  # ** crosses separators
                i += 2
                # swallow a following separator so "**/x" matches "x"
                if i < n and pattern[i] == _SEP:
                    i += 1
                    parts.append(f"(?:.*{re.escape(_SEP)})?")
                continue
            parts.append(f"[^{re.escape(_SEP)}]*")
        elif char == "?":
            parts.append(f"[^{re.escape(_SEP)}]")
        else:
            parts.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(parts) + "$")


def normalize_path(path: str) -> str:
    """Strip a single leading ``./`` and trailing slash; keep everything else.

    ``..`` segments are intentionally preserved — canonicalising them would hide
    traversal bypasses.
    """
    path = path.strip()
    if path.startswith("./"):
        path = path[2:]
    if len(path) > 1 and path.endswith(_SEP):
        path = path[:-1]
    return path


def glob_match(pattern: str, text: str) -> bool:
    """Return True if ``text`` matches the gitignore-style ``pattern``."""
    return _compile(pattern).match(text) is not None


def path_rule_matches(pattern: str, path: str) -> bool:
    """Match a path rule against a candidate path with directory-prefix semantics.

    A pattern with no wildcard also matches everything beneath it (``secrets``
    matches ``secrets/key.pem``), mirroring gitignore directory semantics.
    """
    pat = normalize_path(pattern)
    target = normalize_path(path)
    if glob_match(pat, target):
        return True
    # Directory-prefix match: "secrets" covers "secrets/**".
    return glob_match(pat + "/**", target)
