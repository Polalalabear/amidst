"""D57: pinned legacy ``frames[]`` -> ``records[]`` adapter for ``rgb_index.json``.

The contract key is ``records[]``.  The first r003 export wrote ``frames[]``; those two files
(identified by schema_version AND file SHA-256) are accepted through this in-memory adapter.
Everything else fails closed: both keys, neither key, or ``frames`` from an unpinned file.
The validator never guesses with ``frames ?? records``.  The input file is never rewritten.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

ADAPTER_NAME = "rgb-index-frames-to-records"
ADAPTER_VERSION = "1"
LEGACY_SCHEMA_VERSION = "controlled-scene.rgb-index.v1"
# D57 pin list: (run label, file SHA-256) of the two legacy r003 exports.
_RUN_A = "ctrl-lcorr-s1-a-5fps-v1-r001"
_RUN_B1 = "ctrl-lcorr-s1-b1-5fps-v1-r001"
PINNED_LEGACY_FILE_SHA256: dict[str, str] = {
    "9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47": _RUN_A,
    "a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39": _RUN_B1,
}


@dataclass(frozen=True)
class RgbIndexResolution:
    document: dict[str, Any] | None  # normalised (records[]) document, None when it fails closed
    adapter: dict[str, Any] | None  # applied adapter record for the report
    error_code: str | None
    error_message: str | None


def resolve_rgb_index(raw: dict[str, Any] | None, file_sha256: str | None) -> RgbIndexResolution:
    if raw is None:
        return RgbIndexResolution(None, None, None, None)
    has_records, has_frames = "records" in raw, "frames" in raw
    if has_records and has_frames:
        return RgbIndexResolution(
            None, None, "RGB_INDEX_KEYS_AMBIGUOUS", "records 與 frames 同時存在，fail closed（D57）"
        )
    if not has_records and not has_frames:
        return RgbIndexResolution(
            None, None, "RGB_INDEX_KEYS_MISSING", "records 與 frames 都不存在，fail closed（D57）"
        )
    if has_records:
        return RgbIndexResolution(raw, None, None, None)
    pinned = (
        raw.get("schema_version") == LEGACY_SCHEMA_VERSION
        and file_sha256 in PINNED_LEGACY_FILE_SHA256
    )
    if not pinned:
        return RgbIndexResolution(
            None,
            None,
            "RGB_INDEX_FRAMES_NOT_PINNED",
            "frames[] 只有 schema_version 為 controlled-scene.rgb-index.v1 且檔案 SHA-256 "
            "在 pin 清單內才可轉換；此檔不符，fail closed（D57）",
        )
    normalised = copy.deepcopy(raw)
    normalised["records"] = normalised.pop("frames")
    adapter = {
        "name": ADAPTER_NAME,
        "version": ADAPTER_VERSION,
        "role": "rgb_index",
        "mapping": "frames[] -> records[]",
        "source_file_sha256": file_sha256,
        "source_schema_version": raw.get("schema_version"),
        "pinned_run_id": PINNED_LEGACY_FILE_SHA256[file_sha256 or ""],
    }
    return RgbIndexResolution(normalised, adapter, None, None)
