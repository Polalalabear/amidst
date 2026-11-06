#!/usr/bin/env python3
"""Build a self-contained Q4 True/False human annotation handoff pack (#426, W-A8).

Supports:
- `--synthetic`: generates a deterministic synthetic Q4 T/F blind annotation pack for testing.
- `--safe-pack-dir`: builds from W-C5 safe pack data, or reports `real_pack_status: "UNKNOWN"`
  when the W-C5 safe pack (#416) is not yet available.

Codex REVISE fixes (#436):
1. Complete blind pack separation: the handoff pack contains strictly blind data (no ground truth,
   no system judgments, no answers). System judgments / evaluation claims are written to a
   separate file bound cryptographically via `pack_manifest_sha256` and `sample_set_sha256`.
2. Strict PNG image decoding and validation: rejects corrupted image bytes, non-image bytes,
   disallowed ancillary/text metadata chunks, invalid CRC checksums, and trailing garbage after IEND.
3. Fail-closed guard rejecting any `gt_private/`, `ground_truth`, `visibility`, `depth`,
   or renderer trajectory in inputs or the generated handoff pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zlib
from typing import Any


PACK_SCHEMA_VERSION = "team-review-pack.v1"
PACK_KIND = "q4-tf-annotation-pack-v1"
EVAL_CLAIMS_SCHEMA_VERSION = "team-review-pack.v1"
EVAL_CLAIMS_KIND = "q4-system-judgments-v1"
TEMPLATE_KIND = "q4-tf-answers-v1"
TEMPLATE_REL_PATH = "RETURN/q4_tf_answers_template.json"
DEFAULT_ANNOTATION_SEMANTICS = "TARGET_PRESENCE"
SUPPORTED_PACK_SEMANTICS = ("TARGET_PRESENCE",)
VALID_ANNOTATION_SEMANTICS = ("TARGET_PRESENCE", "CLAIM_VERACITY")
ALLOWED_HUMAN_JUDGMENTS = ("T", "F", "UNKNOWN")
ALLOWED_SYSTEM_JUDGMENTS = ("PRESENT", "ABSENT", "UNKNOWN")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_PNG_CHUNKS = frozenset({
    b"IHDR",
    b"IDAT",
    b"IEND",
})

FORBIDDEN_PATH_TOKENS = (
    "gt_private",
    "ground_truth",
    "visibility",
    "depth",
    "trajectory",
    "trajectories",
    "renderer_track",
    "renderer",
)

FORBIDDEN_TEXT_PATTERN = re.compile(
    r"(?i)(?:gt_private|ground_truth|gt_(?!read\b)[a-z0-9_]*|"
    r"\bvisibility\b|\bdepth\b|\btrajector(?:y|ies)\b|\brenderer(?:_track)?\b|\.blend\b)"
)

SYNTHETIC_CAMERAS = (
    "CAM_ENTRY",
    "CAM_WIDE",
    "CAM_BRANCH",
    "CAM_W1",
    "CAM_W2",
    "CAM_R101_IN",
    "CAM_EXT_CAR",
    "CAM_EXT_CLEAR",
)


class PackBuildError(ValueError):
    """Raised when pack building or boundary validation fails closed."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackBuildError(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_json_strict(raw: bytes) -> Any:
    def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, val in pairs:
            require(key not in result, f"DUPLICATE_JSON_KEY:{key}")
            result[key] = val
        return result

    try:
        text = raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: require(False, "NONFINITE_JSON"),
        )
    except UnicodeDecodeError as exc:
        raise PackBuildError("INVALID_UTF8_JSON") from exc
    except json.JSONDecodeError as exc:
        raise PackBuildError("MALFORMED_JSON") from exc


def validate_rel_path(rel_path: str) -> str:
    require(
        isinstance(rel_path, str) and bool(rel_path) and "\\" not in rel_path and "\0" not in rel_path,
        f"UNSAFE_RELATIVE_PATH:{rel_path}",
    )
    posix = PurePosixPath(rel_path)
    require(
        not posix.is_absolute() and ".." not in posix.parts and posix.as_posix() == rel_path,
        f"UNSAFE_RELATIVE_PATH:{rel_path}",
    )
    for part in posix.parts:
        lower = part.lower()
        require(lower not in {"gt", "private", "gt_private"}, f"FORBIDDEN_PATH_PART:{rel_path}")
        for token in FORBIDDEN_PATH_TOKENS:
            require(token not in lower, f"FORBIDDEN_PATH_TOKEN:{rel_path}")
    return rel_path


def scan_object_for_forbidden_fields(value: Any, path_prefix: str = "$") -> None:
    if isinstance(value, dict):
        for key, subval in value.items():
            require(isinstance(key, str), f"NON_STRING_KEY:{path_prefix}")
            key_lower = key.lower()
            if key_lower == "gt_read":
                require(subval is False, f"GT_READ_MUST_BE_FALSE:{path_prefix}.{key}")
                continue
            for token in FORBIDDEN_PATH_TOKENS:
                require(token not in key_lower, f"FORBIDDEN_FIELD_KEY:{path_prefix}.{key}")
            require(not key_lower.startswith("gt_"), f"FORBIDDEN_GT_KEY:{path_prefix}.{key}")
            scan_object_for_forbidden_fields(subval, f"{path_prefix}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            scan_object_for_forbidden_fields(item, f"{path_prefix}[{idx}]")
    elif isinstance(value, str):
        match = FORBIDDEN_TEXT_PATTERN.search(value)
        require(match is None, f"FORBIDDEN_STRING_CONTENT:{path_prefix}:{match.group(0) if match else ''}")


def validate_png_bytes(raw: bytes, rel_path: str = "frame.png") -> dict[str, Any]:
    """Validate a bounded PNG subset without rewriting the original bytes.

    Supports only IHDR, consecutive IDAT and IEND chunks, non-interlaced
    8/16-bit grayscale or RGB with optional alpha (color types 0, 2, 4, 6).
    Palette, Adam7 and all ancillary chunks fail closed: their structures
    are not implemented by this validator.

    Rejects:
    - Non-PNG signatures or truncated files
    - Appended garbage / non-image bytes after IEND
    - Disallowed chunk types (metadata, EXIF, text chunks)
    - Corrupted CRC checksums
    - Invalid or corrupted IDAT compressed streams
    - Scanline filter byte or pixel dimension corruption
    """
    require(len(raw) >= 8 and raw[:8] == b"\x89PNG\r\n\x1a\n", f"INVALID_PNG_HEADER:{rel_path}")
    offset = 8
    kinds: list[bytes] = []
    compressed: list[bytes] = []
    width = height = bit_depth = color_type = compression = filter_method = interlace = 0
    has_ihdr = False
    has_iend = False

    while offset < len(raw):
        require(offset + 12 <= len(raw), f"PNG_CHUNK_HEADER_TRUNCATED:{rel_path}")
        size = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        end = offset + size + 12
        require(end <= len(raw), f"PNG_CHUNK_DATA_TRUNCATED:{rel_path}:{kind.decode('ascii', errors='replace')}")
        require(kind in ALLOWED_PNG_CHUNKS, f"PNG_CHUNK_DISALLOWED:{rel_path}:{kind.decode('ascii', errors='replace')}")

        data = raw[offset + 8 : end - 4]
        stored_crc = struct.unpack(">I", raw[end - 4 : end])[0]
        calculated_crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        require(stored_crc == calculated_crc, f"PNG_CRC_INVALID:{rel_path}:{kind.decode('ascii', errors='replace')}")

        if kind == b"IHDR":
            require(not has_ihdr and size == 13 and not kinds, f"PNG_IHDR_INVALID:{rel_path}")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data)
            require(width > 0 and height > 0, f"PNG_INVALID_DIMENSIONS:{rel_path}")
            require(bit_depth in (8, 16), f"PNG_UNSUPPORTED_BIT_DEPTH:{rel_path}:{bit_depth}")
            require(color_type in (0, 2, 4, 6), f"PNG_UNSUPPORTED_COLOR_TYPE:{rel_path}:{color_type}")
            require(
                compression == 0 and filter_method == 0 and interlace == 0,
                f"PNG_INVALID_IHDR_PARAMETERS:{rel_path}",
            )
            has_ihdr = True
        elif kind == b"IDAT":
            require(has_ihdr and not has_iend, f"PNG_IDAT_BEFORE_IHDR_OR_AFTER_IEND:{rel_path}")
            compressed.append(data)
        elif kind == b"IEND":
            require(has_ihdr and bool(compressed), f"PNG_IEND_WITHOUT_IDAT:{rel_path}")
            require(size == 0, f"PNG_IEND_NONEMPTY:{rel_path}")
            require(end == len(raw), f"PNG_TRAILING_GARBAGE_AFTER_IEND:{rel_path}")
            has_iend = True

        kinds.append(kind)
        offset = end

    require(has_ihdr and has_iend and kinds[-1] == b"IEND", f"PNG_INCOMPLETE_CHUNKS:{rel_path}")

    try:
        decoder = zlib.decompressobj()
        decompressed = decoder.decompress(b"".join(compressed)) + decoder.flush()
    except zlib.error as exc:
        raise PackBuildError(f"PNG_DECOMPRESSION_FAILED:{rel_path}") from exc
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, f"PNG_DECODER_UNCONSUMED_DATA:{rel_path}")

    if interlace == 0:
        channels_map = {0: 1, 2: 3, 4: 2, 6: 4}
        channels = channels_map[color_type]
        bytes_per_sample = bit_depth // 8 if bit_depth >= 8 else 1
        line_bytes = 1 + width * channels * bytes_per_sample
        expected_len = height * line_bytes
        require(
            len(decompressed) == expected_len,
            f"PNG_DECOMPRESSED_SIZE_MISMATCH:{rel_path}:{len(decompressed)}!={expected_len}",
        )
        for row_idx in range(height):
            filter_type = decompressed[row_idx * line_bytes]
            require(filter_type <= 4, f"PNG_INVALID_FILTER_TYPE:{rel_path}:row_{row_idx}={filter_type}")

    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "byte_length": len(raw),
    }


def scan_bytes_for_forbidden_content(raw: bytes, rel_path: str) -> None:
    validate_rel_path(rel_path)
    if rel_path.endswith(".png"):
        validate_png_bytes(raw, rel_path)
        return
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackBuildError(f"INVALID_UTF8_TEXT:{rel_path}") from exc
    if text.lstrip().startswith(("{", "[")):
        parsed = parse_json_strict(raw)
        scan_object_for_forbidden_fields(parsed, rel_path)
    match = FORBIDDEN_TEXT_PATTERN.search(text)
    require(match is None, f"FORBIDDEN_TEXT_CONTENT:{rel_path}:{match.group(0) if match else ''}")


def scan_directory_for_forbidden_paths_and_content(root: Path) -> None:
    root = Path(root).resolve()
    require(root.is_dir(), "SCAN_ROOT_NOT_DIRECTORY")
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"SYMLINK_FORBIDDEN:{path}")
        rel = path.relative_to(root).as_posix()
        validate_rel_path(rel)
        if path.is_file():
            scan_bytes_for_forbidden_content(path.read_bytes(), rel)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def make_synthetic_png(seed_label: str) -> bytes:
    """Create a deterministic valid 2x2 RGB PNG image without textual metadata chunks."""
    digest = hashlib.sha256(seed_label.encode("utf-8")).digest()
    width, height = 2, 2
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type 0 (None)
        for x in range(width):
            offset = ((y * width + x) * 3) % (len(digest) - 3)
            rows.extend(digest[offset : offset + 3])
    idat = zlib.compress(bytes(rows), level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def generate_synthetic_samples(seed: str = "q4-tf-v1-seed", count: int = 8) -> list[dict[str, Any]]:
    require(isinstance(seed, str) and bool(seed.strip()), "INVALID_SEED")
    require(isinstance(count, int) and count >= 3, "SYNTHETIC_SAMPLE_COUNT_TOO_SMALL")
    judgments_cycle = ("PRESENT", "ABSENT", "PRESENT", "ABSENT", "UNKNOWN", "PRESENT", "ABSENT", "UNKNOWN")
    targets_cycle = (
        "紅衣人物 (person, red)",
        "藍衣人物 (person, blue)",
        "紅衣人物 (person, red)",
        "深色上衣人物 (person, dark)",
        "紅衣人物 (person, red)",
        "白衣人物 (person, white)",
        "黑衣人物 (person, black)",
        "灰衣人物 (person, grey)",
    )
    samples: list[dict[str, Any]] = []
    for idx in range(count):
        sample_id = f"Q4_S{idx + 1:04d}"
        camera_id = SYNTHETIC_CAMERAS[idx % len(SYNTHETIC_CAMERAS)]
        frame_index = 10 + idx * 5
        timestamp_us = frame_index * 100_000
        target_query = targets_cycle[idx % len(targets_cycle)]
        statement = f"此格畫面（{camera_id} frame {frame_index}）中是否出現目標：{target_query}？"
        system_judgment = judgments_cycle[idx % len(judgments_cycle)]
        png_bytes = make_synthetic_png(f"{seed}:{sample_id}:{camera_id}:{frame_index}")
        prediction_token = f"{seed}:pred:{sample_id}:{system_judgment}".encode("utf-8")
        samples.append(
            {
                "sample_id": sample_id,
                "run_id": "SYNTHETIC_R004_A4_1",
                "clock_id": "CLOCK_SYNTHETIC_A4_1",
                "camera_id": camera_id,
                "frame_index": frame_index,
                "timestamp_us": timestamp_us,
                "target_query": target_query,
                "statement": statement,
                "system_judgment": system_judgment,
                "prediction_sha256": sha256_bytes(prediction_token),
                "frame_bytes": png_bytes,
                "frame_sha256": sha256_bytes(png_bytes),
            }
        )
    return samples


def _render_pack_readme(
    *,
    pack_id: str,
    source_mode: str,
    real_pack_status: str,
    sample_set_sha256: str,
    template_sha256: str,
    public_samples: list[dict[str, Any]],
    annotation_semantics: str = DEFAULT_ANNOTATION_SEMANTICS,
) -> bytes:
    mode_note = (
        "本包為 SYNTHETIC 合成測試盲測標註包，僅供驗證 Q4 T/F 標註與計分流程，不代表真實模型或正式 W-C5 評測結果。"
        if source_mode == "SYNTHETIC"
        else "本包由 W-C5 安全資料包產生，供組員獨立進行 Q4 單格畫面 T/F 盲測標註。"
    )
    rows_md = "\n".join(
        f"| `{s['sample_id']}` | `{s['camera_id']}` | `{s['frame_index']}` | `{s['frame_file']}` | `{s['frame_sha256'][:16]}...` | {s['target_query']} |"
        for s in public_samples
    )
    text = f"""# Q4 正式 T／F 組員盲測標註包（{pack_id}）

- **資料模式（`source_mode`）**：`{source_mode}`
- **正式 W-C5 資料狀態（`real_pack_status`）**：`{real_pack_status}`
- **樣本集合校驗碼（`sample_set_sha256`）**：`{sample_set_sha256}`
- **空白模板校驗碼（`template_sha256`）**：`{template_sha256}`
- **說明**：{mode_note}
- **盲測原則**：本標註包為嚴格盲測交付包，**不包含**任何系統模型判定（`PRESENT`／`ABSENT`／`UNKNOWN`）或真實標籤。評估端標準答案透過分離之 evaluation claims 密碼學綁定，確保人工審查完全客觀獨立。
- **標註語意綁定（annotation_semantics）**：`{annotation_semantics}`（標註包、作答模板與回件皆嚴格綁定此語意；交付包限定 TARGET_PRESENCE）


## 工作內容

1. 請檢視 `frames/` 目錄下對應編號的單格相機畫面，針對每筆樣本的 `target_query` 與 `statement` 進行獨立 True／False（T／F）判定。
2. 判定值（`human_judgment`）僅限填寫以下三種字串之一：
   - `"T"`：該格畫面中**明確可見**題目指定之目標人物／條件（在 TARGET_PRESENCE 語意下對應 PRESENT）。
   - `"F"`：該格畫面中**未出現**題目指定之目標人物／條件（在 TARGET_PRESENCE 語意下對應 ABSENT）。
   - `"UNKNOWN"`：畫面模糊、嚴重遮擋或資訊不足，**無法確定**目標是否出現。
3. 本標註僅針對單格影像可見證據，不評估跨鏡頭身分同一性、盲區路線或物理碰撞安全。

## 要提交項目

- 請將空白模板 `RETURN/q4_tf_answers_template.json` 複製為：
  - `RETURN/q4_tf_answers_<組員代號>.json`（例如 `RETURN/q4_tf_answers_annotator1.json`）
- 填寫頂層 `annotator_id`、`completed_at` 以及每筆樣本的 `human_judgment`（`"T"`、`"F"` 或 `"UNKNOWN"`）與選填 `notes`。
- 完成後將整個標註包目錄（含 `RETURN/q4_tf_answers_<組員代號>.json`）交回評估端。

## 操作步驟

1. 確認本目錄包含 `MANIFEST.json`、`README.md`、`frames/*.png` 與 `RETURN/q4_tf_answers_template.json`。
2. 複製 `RETURN/q4_tf_answers_template.json` 為 `RETURN/q4_tf_answers_<組員代號>.json`，保留原始模板檔不變。
3. 依序開啟 `answers` 內的 `frame_file` 圖檔，填寫 `human_judgment`（`"T"`、`"F"` 或 `"UNKNOWN"`）。
4. 切勿修改 `sample_id`、`camera_id`、`frame_index`、`frame_file`、`frame_sha256`、`target_query`、`statement` 等鎖定欄位。
5. 儲存為 UTF-8 JSON，確認無語法錯誤且無未填寫之空字串。

## RETURN/ 繳交規範

- 回件檔必須置於 `RETURN/` 資料夾下，且檔名不得為 `q4_tf_answers_template.json`。
- 嚴禁在標註包或回件中加入任何私有真值、可見度、深度或渲染器軌跡欄位。
- 計分工具會校驗 `MANIFEST.json` 與所有樣本 SHA-256；若鎖定欄位遭竄改、樣本缺漏或判定值無效，將以 Fail-Closed 拒絕計分。

## 樣本清單與 SHA-256 校驗

| 樣本編號 | 相機 | 影格 | 圖檔路徑 | 圖檔 SHA-256（前16碼） | 查詢目標 |
| --- | --- | --- | --- | --- | --- |
{rows_md}
"""
    return text.encode("utf-8")


def _load_safe_pack_samples(safe_pack_dir: Path) -> list[dict[str, Any]] | None:
    """Inspect `--safe-pack-dir`. Reject forbidden content; return None if W-C5 pack is absent."""
    safe_pack_dir = Path(safe_pack_dir)
    if not safe_pack_dir.exists():
        return None
    require(safe_pack_dir.is_dir() and not safe_pack_dir.is_symlink(), "SAFE_PACK_DIR_INVALID")
    scan_directory_for_forbidden_paths_and_content(safe_pack_dir)

    samples_file = safe_pack_dir / "q4_safe_samples.json"
    if not samples_file.is_file():
        return None

    doc = parse_json_strict(samples_file.read_bytes())
    scan_object_for_forbidden_fields(doc, "q4_safe_samples.json")
    require(isinstance(doc, dict) and doc.get("gt_read") is False, "SAFE_PACK_GT_READ_REQUIRED_FALSE")
    raw_samples = doc.get("samples")
    require(isinstance(raw_samples, list) and len(raw_samples) > 0, "SAFE_PACK_SAMPLES_EMPTY")

    loaded: list[dict[str, Any]] = []
    for item in raw_samples:
        require(isinstance(item, dict), "SAFE_PACK_SAMPLE_NOT_OBJECT")
        scan_object_for_forbidden_fields(item, "safe_sample")
        frame_rel = validate_rel_path(str(item.get("frame_file", "")))
        frame_path = safe_pack_dir / frame_rel
        require(frame_path.is_file() and not frame_path.is_symlink(), f"SAFE_PACK_FRAME_MISSING:{frame_rel}")
        frame_bytes = frame_path.read_bytes()
        scan_bytes_for_forbidden_content(frame_bytes, frame_rel)
        expected_sha = item.get("frame_sha256")
        actual_sha = sha256_bytes(frame_bytes)
        require(
            isinstance(expected_sha, str) and SHA256_RE.match(expected_sha) and actual_sha == expected_sha,
            f"SAFE_PACK_FRAME_SHA_MISMATCH:{frame_rel}",
        )
        loaded.append(
            {
                "sample_id": str(item["sample_id"]),
                "run_id": str(item["run_id"]),
                "clock_id": str(item["clock_id"]),
                "camera_id": str(item["camera_id"]),
                "frame_index": int(item["frame_index"]),
                "timestamp_us": int(item.get("timestamp_us", int(item["frame_index"]) * 100_000)),
                "target_query": str(item["target_query"]),
                "statement": str(item["statement"]),
                "system_judgment": str(item["system_judgment"]),
                "prediction_sha256": str(item["prediction_sha256"]),
                "frame_bytes": frame_bytes,
                "frame_sha256": actual_sha,
            }
        )
    return loaded


def verify_handoff_pack(pack_dir: Path | str, expected_manifest_sha256: str | None = None) -> dict[str, Any]:
    """Verify a generated Q4 T/F blind annotation handoff pack fail-closed."""
    root = Path(pack_dir).resolve()
    require(root.is_dir() and not root.is_symlink(), "PACK_DIR_INVALID")
    scan_directory_for_forbidden_paths_and_content(root)

    # Ensure no claims or judgments exist inside the blind annotator pack
    require(not (root / "claims").exists(), "PACK_NOT_BLIND:CLAIMS_DIR_FOUND")

    manifest_path = root / "MANIFEST.json"
    require(manifest_path.is_file(), "MANIFEST_MISSING")
    manifest_raw = manifest_path.read_bytes()
    actual_manifest_sha = sha256_bytes(manifest_raw)
    if expected_manifest_sha256 is not None:
        require(
            isinstance(expected_manifest_sha256, str)
            and SHA256_RE.match(expected_manifest_sha256)
            and actual_manifest_sha == expected_manifest_sha256,
            "MANIFEST_SHA256_MISMATCH",
        )

    manifest = parse_json_strict(manifest_raw)
    scan_object_for_forbidden_fields(manifest, "MANIFEST.json")
    require(
        isinstance(manifest, dict)
        and manifest.get("schema_version") == PACK_SCHEMA_VERSION
        and manifest.get("pack_kind") == PACK_KIND
        and manifest.get("gt_read") is False,
        "MANIFEST_HEADER_INVALID",
    )

    files_map = manifest.get("files")
    require(isinstance(files_map, dict) and bool(files_map), "MANIFEST_FILES_INVALID")
    for rel_path, expected_sha in files_map.items():
        validate_rel_path(rel_path)
        require("claims" not in rel_path.lower(), f"PACK_NOT_BLIND:CLAIMS_IN_MANIFEST:{rel_path}")
        require(isinstance(expected_sha, str) and bool(SHA256_RE.match(expected_sha)), f"INVALID_FILE_PIN:{rel_path}")
        file_path = root / rel_path
        require(file_path.is_file() and not file_path.is_symlink(), f"PACK_FILE_MISSING:{rel_path}")
        raw = file_path.read_bytes()
        require(sha256_bytes(raw) == expected_sha, f"PACK_FILE_SHA256_MISMATCH:{rel_path}")
        scan_bytes_for_forbidden_content(raw, rel_path)

    readme_text = (root / "README.md").read_text(encoding="utf-8")
    for required_section in ("## 工作內容", "## 要提交項目", "## 操作步驟"):
        require(required_section in readme_text, f"README_SECTION_MISSING:{required_section}")

    template_path = root / TEMPLATE_REL_PATH
    require(template_path.is_file(), "TEMPLATE_FILE_MISSING")
    template_doc = parse_json_strict(template_path.read_bytes())
    require(
        template_doc.get("schema_version") == PACK_SCHEMA_VERSION
        and template_doc.get("template_kind") == TEMPLATE_KIND
        and template_doc.get("sample_set_sha256") == manifest.get("sample_set_sha256"),
        "TEMPLATE_METADATA_MISMATCH",
    )
    if "annotation_semantics" in manifest:
        require(
            manifest["annotation_semantics"] in SUPPORTED_PACK_SEMANTICS,
            f"INVALID_MANIFEST_ANNOTATION_SEMANTICS:{manifest.get('annotation_semantics')}",
        )
    if "annotation_semantics" in template_doc:
        require(
            template_doc["annotation_semantics"] in SUPPORTED_PACK_SEMANTICS,
            f"INVALID_TEMPLATE_ANNOTATION_SEMANTICS:{template_doc.get('annotation_semantics')}",
        )
        if "annotation_semantics" in manifest:
            require(
                template_doc["annotation_semantics"] == manifest["annotation_semantics"],
                "TEMPLATE_MANIFEST_SEMANTICS_MISMATCH",
            )

    return {
        "status": "VALID",
        "manifest_sha256": actual_manifest_sha,
        "manifest": manifest,
    }


def build_q4_tf_annotation_pack(
    output_dir: Path | str,
    *,
    synthetic: bool = False,
    safe_pack_dir: Path | str | None = None,
    samples: list[dict[str, Any]] | None = None,
    seed: str = "q4-tf-v1-seed",
    sample_count: int = 8,
    pack_id: str | None = None,
    system_judgments_out: Path | str | None = None,
    annotation_semantics: str = DEFAULT_ANNOTATION_SEMANTICS,
) -> dict[str, Any]:
    """Build a Q4 T/F blind annotation handoff pack and separate evaluation claims file."""
    require(not (synthetic and safe_pack_dir is not None), "CONFLICTING_SOURCE_MODES")
    require(synthetic or safe_pack_dir is not None or samples is not None, "SOURCE_MODE_REQUIRED")
    require(
        annotation_semantics in VALID_ANNOTATION_SEMANTICS,
        f"UNSUPPORTED_ANNOTATION_SEMANTICS:{annotation_semantics}",
    )
    require(
        annotation_semantics in SUPPORTED_PACK_SEMANTICS,
        f"UNSUPPORTED_PACK_ANNOTATION_SEMANTICS:{annotation_semantics}:pack_generation_restricted_to_TARGET_PRESENCE",
    )

    output_path = Path(output_dir).resolve()
    require(not output_path.exists(), "OUTPUT_DIR_ALREADY_EXISTS")

    resolved_claims_path = (
        Path(system_judgments_out).resolve()
        if system_judgments_out is not None
        else output_path.parent / f"{output_path.name}.eval_claims.json"
    )
    require(
        not resolved_claims_path.is_relative_to(output_path),
        "SYSTEM_CLAIMS_CANNOT_BE_INSIDE_BLIND_PACK",
    )
    require(not resolved_claims_path.exists(), "SYSTEM_CLAIMS_OUT_ALREADY_EXISTS")

    if safe_pack_dir is not None:
        loaded_samples = _load_safe_pack_samples(Path(safe_pack_dir))
        if loaded_samples is None:
            output_path.mkdir(parents=True, exist_ok=False)
            unknown_report = {
                "schema_version": PACK_SCHEMA_VERSION,
                "pack_kind": PACK_KIND,
                "status": "UNKNOWN",
                "source_mode": "SAFE_PACK",
                "real_pack_status": "UNKNOWN",
                "reason": "W_C5_SAFE_PACK_ABSENT",
                "blocking_issue": "#416",
                "safe_pack_dir": str(Path(safe_pack_dir)),
                "pack_dir": str(output_path),
                "evaluation_eligible": False,
                "gt_read": False,
            }
            status_bytes = pretty_json_bytes(unknown_report)
            (output_path / "REAL_PACK_STATUS.json").write_bytes(status_bytes)
            unknown_report["status_file_sha256"] = sha256_bytes(status_bytes)
            return unknown_report
        raw_samples = loaded_samples
        source_mode = "SAFE_PACK"
        real_pack_status = "READY"
        evaluation_eligible = True
    else:
        raw_samples = samples if samples is not None else generate_synthetic_samples(seed=seed, count=sample_count)
        source_mode = "SYNTHETIC"
        real_pack_status = "SYNTHETIC_ONLY"
        evaluation_eligible = False

    require(isinstance(raw_samples, list) and len(raw_samples) > 0, "EMPTY_SAMPLES")

    seen_ids: set[str] = set()
    public_samples: list[dict[str, Any]] = []
    system_judgments: list[dict[str, Any]] = []
    payload_files: dict[str, bytes] = {}

    for idx, item in enumerate(raw_samples):
        require(isinstance(item, dict), f"SAMPLE_NOT_OBJECT:{idx}")
        scan_object_for_forbidden_fields(item, f"samples[{idx}]")

        sample_id = str(item.get("sample_id", "")).strip()
        require(
            bool(sample_id) and "/" not in sample_id and "\\" not in sample_id and sample_id not in seen_ids,
            f"INVALID_OR_DUPLICATE_SAMPLE_ID:{sample_id}",
        )
        seen_ids.add(sample_id)

        camera_id = str(item.get("camera_id", "")).strip()
        require(bool(camera_id) and "/" not in camera_id and "\\" not in camera_id, f"INVALID_CAMERA_ID:{camera_id}")
        run_id = str(item.get("run_id", "")).strip()
        clock_id = str(item.get("clock_id", "")).strip()
        target_query = str(item.get("target_query", "")).strip()
        statement = str(item.get("statement", "")).strip()
        require(all(bool(x) for x in (run_id, clock_id, target_query, statement)), f"MISSING_SAMPLE_TEXT:{sample_id}")

        frame_index = item.get("frame_index")
        require(type(frame_index) is int and frame_index >= 0, f"INVALID_FRAME_INDEX:{sample_id}")
        timestamp_us = item.get("timestamp_us", frame_index * 100_000)
        require(type(timestamp_us) is int and timestamp_us >= 0, f"INVALID_TIMESTAMP_US:{sample_id}")

        sys_judgment = item.get("system_judgment")
        require(sys_judgment in ALLOWED_SYSTEM_JUDGMENTS, f"INVALID_SYSTEM_JUDGMENT:{sample_id}")

        frame_bytes = item.get("frame_bytes")
        if frame_bytes is None:
            frame_bytes = make_synthetic_png(f"{seed}:{sample_id}:{camera_id}:{frame_index}")
        require(isinstance(frame_bytes, bytes), f"INVALID_FRAME_BYTES:{sample_id}")
        frame_rel = validate_rel_path(f"frames/{sample_id}.png")
        scan_bytes_for_forbidden_content(frame_bytes, frame_rel)
        frame_sha = sha256_bytes(frame_bytes)
        if "frame_sha256" in item:
            require(item["frame_sha256"] == frame_sha, f"FRAME_SHA256_MISMATCH:{sample_id}")

        pred_sha = item.get(
            "prediction_sha256",
            sha256_bytes(f"{seed}:pred:{sample_id}:{sys_judgment}".encode("utf-8")),
        )
        require(isinstance(pred_sha, str) and bool(SHA256_RE.match(pred_sha)), f"INVALID_PREDICTION_SHA256:{sample_id}")

        payload_files[frame_rel] = frame_bytes

        # Public samples contain NO system judgments or model predictions
        public_samples.append(
            {
                "sample_id": sample_id,
                "run_id": run_id,
                "clock_id": clock_id,
                "camera_id": camera_id,
                "frame_index": frame_index,
                "timestamp_us": timestamp_us,
                "frame_file": frame_rel,
                "frame_sha256": frame_sha,
                "target_query": target_query,
                "statement": statement,
            }
        )

        # Separate system judgments record for evaluation key
        system_judgments.append(
            {
                "sample_id": sample_id,
                "run_id": run_id,
                "clock_id": clock_id,
                "camera_id": camera_id,
                "frame_index": frame_index,
                "frame_sha256": frame_sha,
                "system_judgment": sys_judgment,
                "prediction_sha256": pred_sha,
            }
        )

    resolved_pack_id = pack_id or (
        f"q4-tf-synthetic-{seed}" if source_mode == "SYNTHETIC" else f"q4-tf-wc5-{seed}"
    )
    sample_set_sha256 = sha256_bytes(canonical_json_bytes(public_samples))

    template_doc = {
        "schema_version": PACK_SCHEMA_VERSION,
        "template_kind": TEMPLATE_KIND,
        "pack_id": resolved_pack_id,
        "source_mode": source_mode,
        "real_pack_status": real_pack_status,
        "annotation_semantics": annotation_semantics,
        "sample_set_sha256": sample_set_sha256,
        "annotator_id": "",
        "completed_at": "",
        "allowed_judgments": list(ALLOWED_HUMAN_JUDGMENTS),
        "answers": [
            {
                **sample,
                "human_judgment": "",
                "notes": "",
            }
            for sample in public_samples
        ],
    }
    template_bytes = pretty_json_bytes(template_doc)
    template_sha256 = sha256_bytes(template_bytes)
    payload_files[TEMPLATE_REL_PATH] = template_bytes

    payload_files["RETURN/README.md"] = (
        "# RETURN 回件目錄\n\n"
        "請將 `q4_tf_answers_template.json` 複製為 `q4_tf_answers_<組員代號>.json` 並填寫完畢後置於此目錄。\n"
        "請勿刪除或修改 `q4_tf_answers_template.json`。\n"
    ).encode("utf-8")

    readme_bytes = _render_pack_readme(
        pack_id=resolved_pack_id,
        source_mode=source_mode,
        real_pack_status=real_pack_status,
        sample_set_sha256=sample_set_sha256,
        template_sha256=template_sha256,
        public_samples=public_samples,
        annotation_semantics=annotation_semantics,
    )
    payload_files["README.md"] = readme_bytes

    for rel_path, raw in payload_files.items():
        scan_bytes_for_forbidden_content(raw, rel_path)

    files_manifest = {rel: sha256_bytes(raw) for rel, raw in sorted(payload_files.items())}
    manifest_doc = {
        "schema_version": PACK_SCHEMA_VERSION,
        "pack_kind": PACK_KIND,
        "pack_id": resolved_pack_id,
        "source_mode": source_mode,
        "real_pack_status": real_pack_status,
        "evaluation_eligible": evaluation_eligible,
        "gt_read": False,
        "seed": seed,
        "sample_count": len(public_samples),
        "annotation_semantics": annotation_semantics,
        "sample_set_sha256": sample_set_sha256,
        "template_file": TEMPLATE_REL_PATH,
        "template_sha256": template_sha256,
        "samples": public_samples,
        "files": files_manifest,
    }
    manifest_bytes = pretty_json_bytes(manifest_doc)
    scan_bytes_for_forbidden_content(manifest_bytes, "MANIFEST.json")
    manifest_sha256 = sha256_bytes(manifest_bytes)

    # Write blind annotator handoff pack
    output_path.mkdir(parents=True, exist_ok=False)
    for rel_path, raw in sorted(payload_files.items()):
        target = output_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    with (output_path / "MANIFEST.json").open("xb") as stream:
        stream.write(manifest_bytes)

    verify_handoff_pack(output_path, expected_manifest_sha256=manifest_sha256)

    # Write separate evaluation claims file outside the blind pack
    eval_claims_doc = {
        "schema_version": EVAL_CLAIMS_SCHEMA_VERSION,
        "claims_kind": EVAL_CLAIMS_KIND,
        "pack_id": resolved_pack_id,
        "pack_manifest_sha256": manifest_sha256,
        "sample_set_sha256": sample_set_sha256,
        "annotation_semantics": annotation_semantics,
        "source_mode": source_mode,
        "gt_read": False,
        "sample_count": len(system_judgments),
        "judgments": system_judgments,
    }
    eval_claims_bytes = pretty_json_bytes(eval_claims_doc)
    scan_bytes_for_forbidden_content(eval_claims_bytes, resolved_claims_path.name)
    eval_claims_sha256 = sha256_bytes(eval_claims_bytes)
    resolved_claims_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_claims_path.write_bytes(eval_claims_bytes)

    return {
        "schema_version": PACK_SCHEMA_VERSION,
        "pack_kind": PACK_KIND,
        "status": "READY",
        "pack_id": resolved_pack_id,
        "pack_dir": str(output_path),
        "source_mode": source_mode,
        "real_pack_status": real_pack_status,
        "evaluation_eligible": evaluation_eligible,
        "gt_read": False,
        "annotation_semantics": annotation_semantics,
        "sample_count": len(public_samples),
        "sample_set_sha256": sample_set_sha256,
        "template_file": TEMPLATE_REL_PATH,
        "template_sha256": template_sha256,
        "manifest_sha256": manifest_sha256,
        "system_judgments_file": str(resolved_claims_path),
        "system_judgments_sha256": eval_claims_sha256,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", "--output", dest="output_dir", required=True, type=Path)
    parser.add_argument(
        "--system-judgments-out",
        type=Path,
        default=None,
        help="Optional destination path for system judgments evaluation file (defaults to <output_dir>.eval_claims.json).",
    )
    parser.add_argument("--synthetic", action="store_true", help="Build a deterministic synthetic Q4 T/F pack.")
    parser.add_argument("--safe-pack-dir", type=Path, help="Path to W-C5 safe pack directory.")
    parser.add_argument(
        "--annotation-semantics",
        choices=list(VALID_ANNOTATION_SEMANTICS),
        default=DEFAULT_ANNOTATION_SEMANTICS,
        help="Explicit annotation semantics bound to the pack and template (default: TARGET_PRESENCE).",
    )
    parser.add_argument("--seed", default="q4-tf-v1-seed", help="Deterministic sampling/generation seed.")
    parser.add_argument("--sample-count", type=int, default=8, help="Number of synthetic samples to generate.")
    parser.add_argument("--receipt", type=Path, help="Optional path to write the build receipt JSON.")
    args = parser.parse_args(argv)

    try:
        result = build_q4_tf_annotation_pack(
            args.output_dir,
            synthetic=args.synthetic,
            safe_pack_dir=args.safe_pack_dir,
            seed=args.seed,
            sample_count=args.sample_count,
            system_judgments_out=args.system_judgments_out,
            annotation_semantics=args.annotation_semantics,
        )
        if args.receipt is not None:
            require(not args.receipt.exists(), "RECEIPT_ALREADY_EXISTS")
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(pretty_json_bytes(result))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (PackBuildError, OSError, ValueError, TypeError) as exc:
        err = {
            "status": "INVALID",
            "reason": str(exc) if isinstance(exc, PackBuildError) else "BUILD_FAILED",
        }
        print(json.dumps(err, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
