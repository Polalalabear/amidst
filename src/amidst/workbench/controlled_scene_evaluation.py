"""Explicit offline frozen-evaluation entry. Never imported by the formal service."""

from pathlib import Path
from typing import Any

from amidst.workbench.controlled_scene_data import checked_hash, parse_json, read_regular
from amidst.workbench.scene_errors import DataIntegrityError


def load_private_manifest_for_frozen_evaluation(
    private_root: Path, *, manifest_sha256: str, frozen_output: bytes,
    frozen_output_sha256: str,
) -> dict[str, Any]:
    """Check frozen bytes first. Does not follow/read GT entries from this manifest."""
    import hashlib

    if hashlib.sha256(frozen_output).hexdigest() != checked_hash(frozen_output_sha256):
        raise DataIntegrityError("FROZEN_OUTPUT_HASH_MISMATCH")
    raw = read_regular(private_root, "production_manifest.json")
    if hashlib.sha256(raw).hexdigest() != checked_hash(manifest_sha256):
        raise DataIntegrityError("PRIVATE_MANIFEST_HASH_MISMATCH")
    return parse_json(raw)
