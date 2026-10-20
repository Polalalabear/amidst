"""Input, safe/private separation and hash-format rules."""

from __future__ import annotations

import re
from typing import Any

from .context import Context, is_hex64, iter_nodes
from .contract import (
    ALLOWLIST_REQUIRED,
    ALLOWLIST_ROLES,
    FORBIDDEN_KEY_TOKENS,
    FORBIDDEN_KEYS,
    FORBIDDEN_PATH_SEGMENTS,
    FORBIDDEN_VALUE_FRAGMENTS,
    NULLABLE_HASH_KEYS,
    SAFE_FILENAMES,
)
from .report import Collector, rule

_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


@rule(
    "IO-001",
    "輸入檔是 allowlist 內的 safe 檔，路徑不指向 private、不是 symlink（先於任何 IO）",
    "契約 §3.0、§7 路徑防護",
    "io",
)
def io_inputs(ctx: Context, out: Collector) -> None:
    for code, scope, field_, message in ctx.load_issues:
        if code in (
            "FORBIDDEN_DATA_SCOPE",
            "INPUT_NOT_ALLOWLISTED",
            "INPUT_SYMLINK",
            "INPUT_ESCAPES_BUNDLE",
            "INPUT_MISSING",
        ):
            out.err(code, scope, field_, message)
    for role in ("scene_static", "manifest", "rgb_index", "runtime_profile"):
        if role not in ctx.docs and not any(
            i[1] == role for i in ctx.load_issues
        ):  # in-memory call with no document
            out.err("INPUT_MISSING", role, SAFE_FILENAMES[role], f"{SAFE_FILENAMES[role]} 未提供")
    if ctx.cameras_doc is None and not (isinstance(ctx.static, dict) and "cameras" in ctx.static):
        if not any(i[1] == "cameras" for i in ctx.load_issues):
            out.err(
                "INPUT_MISSING",
                "cameras",
                "cameras.json",
                "cameras.json 未提供，scene_static.json 也沒有 cameras[]（U02）",
            )


@rule("IO-002", "JSON 可解析、無 NaN／Infinity、無重複 key、頂層為物件", "契約 §2.1", "io")
def io_json(ctx: Context, out: Collector) -> None:
    for code, scope, field_, message in ctx.load_issues:
        if code in ("JSON_INVALID", "JSON_NOT_OBJECT"):
            out.err(code, scope, field_, message)


def _key_forbidden(key: str) -> bool:
    lowered = key.lower()
    if lowered in FORBIDDEN_KEYS:
        return True
    return bool(set(re.split(r"[^a-z0-9]+", lowered)) & FORBIDDEN_KEY_TOKENS)


@rule(
    "SPLIT-001",
    "safe 檔不含 private 欄位（actor、route、seed、GT、mask、產製設定…）",
    "契約 §3.0、§3.10、§3.8、§3.9、§7",
)
def split_keys(ctx: Context, out: Collector) -> None:
    for role, doc in ctx.docs.items():
        for path, key, _ in iter_nodes(doc):
            if key is not None and _key_forbidden(key):
                out.err(
                    "PRIVATE_FIELD_IN_SAFE_FILE",
                    role,
                    path,
                    f"safe 檔 {role} 出現 private 欄位名 {key!r}；不得放進 safe bundle",
                )


def _bad_string(value: str) -> str | None:
    lowered = value.lower()
    for fragment in FORBIDDEN_VALUE_FRAGMENTS:
        if fragment in lowered:
            return f"含 private 參照片段 {fragment!r}"
    if value.startswith(("/", "~", "\\")) or _DRIVE.match(value) or lowered.startswith("file:"):
        return "是絕對路徑或本機路徑"
    if "/" in value or "\\" in value:
        segments = [s.lower() for s in re.split(r"[\\/]+", value)]
        if ".." in segments:
            return "含路徑穿越 .."
        if set(segments[:-1]) & FORBIDDEN_PATH_SEGMENTS or (
            len(segments) > 1 and segments[0] in FORBIDDEN_PATH_SEGMENTS
        ):
            return "指向 private／derived／assets 路徑段"
    return None


@rule(
    "SPLIT-002",
    "safe 檔不含 private 路徑參照、絕對路徑或路徑穿越；遇到只報錯、不開檔",
    "契約 §3.0、§7 路徑防護（錯誤訊息不回顯私有路徑）",
)
def split_values(ctx: Context, out: Collector) -> None:
    for role, doc in ctx.docs.items():
        for path, _, value in iter_nodes(doc):
            if isinstance(value, str):
                problem = _bad_string(value)
                if problem:
                    # The offending value is not echoed (contract §7).
                    out.err(
                        "PRIVATE_REFERENCE_IN_SAFE_FILE",
                        role,
                        path,
                        f"字串值{problem}；validator 不會開啟它",
                    )


@rule(
    "SPLIT-003",
    "manifest.allowlist 只列 safe 角色與 safe 檔名，hash 格式正確",
    "契約 §3.10 safe manifest 的 allowlist（結構為範本提案，U03）",
)
def split_allowlist(ctx: Context, out: Collector) -> None:
    allowlist = (ctx.manifest or {}).get("allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        out.err("ALLOWLIST_MISSING", "manifest", "$.allowlist", "manifest.allowlist 必須是非空陣列")
        return
    safe_names = set(SAFE_FILENAMES.values()) | {
        "event_A.query.json",
        "event_B1.query.json",
        "event_B2.query.json",
    }
    seen: set[str] = set()
    for index, item in enumerate(allowlist):
        path = f"$.allowlist[{index}]"
        if not isinstance(item, dict):
            out.err("ALLOWLIST_ENTRY_INVALID", "manifest", path, "allowlist 項目必須是物件")
            continue
        for key in ALLOWLIST_REQUIRED:
            if key not in item:
                out.err(
                    "ALLOWLIST_FIELD_MISSING",
                    "manifest",
                    f"{path}.{key}",
                    f"allowlist 項目缺少 {key}",
                )
        role, name = item.get("role"), item.get("filename")
        if role not in ALLOWLIST_ROLES:
            out.err(
                "ALLOWLIST_ROLE_UNKNOWN",
                "manifest",
                f"{path}.role",
                f"role 必須是 {', '.join(ALLOWLIST_ROLES)}",
            )
        if not isinstance(name, str) or name not in safe_names:
            out.err(
                "ALLOWLIST_FILENAME_NOT_SAFE",
                "manifest",
                f"{path}.filename",
                "filename 不是 safe 檔名（只能是 safe 側的 JSON 檔）",
            )
        elif name in seen:
            out.err(
                "ALLOWLIST_DUPLICATE", "manifest", f"{path}.filename", f"allowlist 重複列出 {name}"
            )
        else:
            seen.add(name)
        if "file_sha256" in item and not is_hex64(item["file_sha256"]):
            out.err(
                "HASH_FORMAT",
                "manifest",
                f"{path}.file_sha256",
                "file_sha256 必須是 64 位小寫十六進位",
            )


def _hash_keys(doc: Any) -> list[tuple[str, str, Any]]:
    return [(p, k, v) for p, k, v in iter_nodes(doc) if k is not None and (k.endswith("_sha256"))]


@rule(
    "HSH-001",
    "所有 *_sha256 欄位為 64 位小寫十六進位（approval_sha256／verification_sha256 可為 null）；"
    "hash、source、pin 欄位齊全",
    "契約 §2.1、§3.1、§3.3、§3.4、§3.7、§3.10、§3.11",
)
def hash_format(ctx: Context, out: Collector) -> None:
    for role, doc in ctx.docs.items():
        for path, key, value in _hash_keys(doc):
            if value is None and key in NULLABLE_HASH_KEYS:
                continue
            if not is_hex64(value):
                out.err(
                    "HASH_FORMAT",
                    role,
                    path,
                    f"{key} 必須是 64 位小寫十六進位 sha256"
                    + ("（不可為 null）" if value is None else ""),
                )
    required_pins = [("scene_static", "source_static_sha256"), ("manifest", "source_sha256")]
    for role, key in required_pins:
        doc = ctx.docs.get(role)
        if isinstance(doc, dict) and key not in doc:
            out.err("PIN_FIELD_MISSING", role, f"$.{key}", f"{role} 缺少 {key}")
