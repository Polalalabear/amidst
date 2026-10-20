"""Input guard and JSON loading for the safe bundle.

The guard runs before any IO (contract §7: path checks first, then IO) and never opens a file
whose name or location points at private data.  Only the five allowlisted safe filenames are
ever read; private references found *inside* those files are reported by the rules and never
followed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .contract import PRIVATE_FILENAMES, SAFE_FILENAMES

_PRIVATE_ANYWHERE = frozenset({"private_evaluation", "review_only"})
_PRIVATE_PARENT = frozenset({"gt", "derived", "assets"})


class InputRejected(Exception):
    """The requested input is not an acceptable safe-side file."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed (contract §2.1)")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def check_safe_path(path: Path, expected_name: str, bundle_dir: Path) -> None:
    """Raise ``InputRejected`` unless ``path`` is the allowlisted safe file in the bundle."""
    parts = {p.lower() for p in path.parts}
    parent = path.parent.name.lower()
    if (
        parts & _PRIVATE_ANYWHERE
        or parent in _PRIVATE_PARENT
        or path.name.lower() in PRIVATE_FILENAMES
        or path.name.lower().endswith(".validation.json")
    ):
        raise InputRejected("FORBIDDEN_DATA_SCOPE", "input path points at a private location")
    if path.name != expected_name:
        raise InputRejected("INPUT_NOT_ALLOWLISTED", f"input must be named {expected_name}")
    if path.is_symlink() or bundle_dir.is_symlink():
        raise InputRejected("INPUT_SYMLINK", "symbolic links are not accepted")
    real = Path(os.path.realpath(path))
    if real.parent != Path(os.path.realpath(bundle_dir)):
        raise InputRejected(
            "INPUT_ESCAPES_BUNDLE", "input resolves outside the safe bundle directory"
        )


def load_json_file(path: Path) -> tuple[Any, str]:
    """(document, file_sha256).  Raises ValueError on malformed JSON, NaN or duplicate keys."""
    raw = path.read_bytes()
    doc = json.loads(
        raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys
    )
    return doc, hashlib.sha256(raw).hexdigest()


def load_safe_bundle(
    bundle_dir: Path,
) -> tuple[dict[str, Any], dict[str, str], list[tuple[str, str, str, str]]]:
    """Load the five safe files from ``bundle_dir``.

    Returns (documents by role, file_sha256 by role, load issues).  A missing file is reported as
    an issue (cameras.json may be absent only when scene_static.json carries the cameras, U02).
    """
    docs: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    issues: list[tuple[str, str, str, str]] = []
    for role, name in SAFE_FILENAMES.items():
        path = bundle_dir / name
        try:
            check_safe_path(path, name, bundle_dir)
        except InputRejected as exc:
            issues.append((exc.code, role, name, str(exc)))
            continue
        if not path.is_file():
            issues.append(("INPUT_MISSING", role, name, f"{name} not found in the safe bundle"))
            continue
        try:
            docs[role], hashes[role] = load_json_file(path)
        except (ValueError, UnicodeDecodeError) as exc:
            issues.append(("JSON_INVALID", role, name, str(exc)))
    return docs, hashes, issues
