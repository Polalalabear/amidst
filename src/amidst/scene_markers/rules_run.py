"""Run-level rules: manifest identity, sampling arithmetic, allowlist hashes, rgb_index grid."""

from __future__ import annotations

from typing import Any

from .context import Context, is_int, is_num
from .contract import PREVIEW_RUN_ID_PATTERN, RGB_REF_PATTERN, RUN_ID_PATTERN, SAFE_FILENAMES
from .report import Collector, Skip, rule

_TS_TOL = 1e-6


def _is_preview(ctx: Context) -> bool:
    manifest = ctx.manifest or {}
    return manifest.get("purpose") == "CALIBRATION_PREVIEW" or manifest.get("complete") is False


def _sampling(ctx: Context) -> dict[str, Any]:
    sampling = (ctx.manifest or {}).get("sampling")
    return sampling if isinstance(sampling, dict) else {}


@rule(
    "RUN-001",
    "manifest 身分一致：scene／run／clock，runtime_profile 與 manifest 對齊",
    "契約 §3.10、§4（run ID 與 clock ID 格式）、§3.11",
)
def run_identity(ctx: Context, out: Collector) -> None:
    manifest = ctx.manifest
    if not isinstance(manifest, dict):
        return
    static = ctx.static or {}
    if (
        "scene_id" in manifest
        and "scene_id" in static
        and manifest["scene_id"] != static["scene_id"]
    ):
        out.err(
            "SCENE_ID_MISMATCH",
            "manifest",
            "$.scene_id",
            "manifest.scene_id 與 scene_static.scene_id 不一致",
        )
    if (
        "scene_version" in manifest
        and "scene_version" in static
        and manifest["scene_version"] != static["scene_version"]
    ):
        out.err(
            "SCENE_VERSION_MISMATCH",
            "manifest",
            "$.scene_version",
            "manifest.scene_version 與 scene_static.scene_version 不一致",
        )
    run_id = manifest.get("run_id")
    if isinstance(run_id, str):
        run_match = RUN_ID_PATTERN.match(run_id)
        if not (run_match or PREVIEW_RUN_ID_PATTERN.match(run_id)):
            out.err(
                "RUN_ID_FORMAT",
                "manifest",
                "$.run_id",
                "run_id 格式需為 "
                "ctrl-lcorr-s<scene_version>-<a|b1|b2>-<sampling_version>-r<revision:03d>",
            )
        elif (
            run_match
            and is_int(manifest.get("scene_version"))
            and int(run_match["scene_version"]) != manifest["scene_version"]
        ):
            out.err(
                "RUN_ID_SCENE_VERSION",
                "manifest",
                "$.run_id",
                "run_id 內的 scene_version 與 manifest.scene_version 不一致",
            )
        if "clock_id" in manifest and manifest["clock_id"] != f"clock:{run_id}":
            out.err("CLOCK_ID_FORMAT", "manifest", "$.clock_id", "clock_id 必須是 clock:<run_id>")
    run_bound = [b for b in ctx.run_bindings if b.get("run_id") == run_id]
    if ctx.run_bindings and not run_bound:
        out.err(
            "RUN_NOT_BOUND",
            "cameras",
            "$.run_bindings",
            "run_bindings[] 沒有這個 manifest.run_id 的綁定",
        )
    for binding in run_bound:
        if binding.get("clock_id") != manifest.get("clock_id"):
            out.err(
                "CLOCK_ID_MISMATCH",
                "cameras",
                "$.run_bindings",
                "綁定的 clock_id 與 manifest.clock_id 不一致",
                binding.get("camera_id"),
            )
    profile = ctx.runtime_profile
    if isinstance(profile, dict):
        for key in ("scene_id", "run_id"):
            if key in profile and key in manifest and profile[key] != manifest[key]:
                out.err(
                    "PROFILE_IDENTITY",
                    "runtime_profile",
                    f"$.{key}",
                    f"runtime_profile.{key} 與 manifest 不一致",
                )
        if "sampling" in profile and profile["sampling"] != manifest.get("sampling"):
            out.err(
                "PROFILE_SAMPLING",
                "runtime_profile",
                "$.sampling",
                "runtime_profile 的 grid 與 manifest.sampling 不一致",
            )


@rule(
    "RUN-002",
    "取樣算術：duration×fps 為整數、等於每鏡 sample 數、last_timestamp_s 與 duration_s 分開",
    "契約 §2（時間區間、半開 [0, duration_s)）、§3.10",
)
def run_sampling(ctx: Context, out: Collector) -> None:
    s = _sampling(ctx)
    fps, duration, count, last = (
        s.get("fps"),
        s.get("duration_s"),
        s.get("sample_count_per_camera"),
        s.get("last_timestamp_s"),
    )
    if not (is_num(fps) and fps > 0 and is_num(duration) and duration > 0):
        return  # SCH-009 reports it
    product = duration * fps
    if abs(product - round(product)) > 1e-9:
        out.err(
            "DURATION_NOT_INTEGER_GRID",
            "manifest",
            "$.sampling",
            f"duration_s×fps={product} 必須是整數",
        )
    elif is_int(count) and count != round(product):
        out.err(
            "SAMPLE_COUNT_MISMATCH",
            "manifest",
            "$.sampling.sample_count_per_camera",
            f"sample_count_per_camera 應為 duration_s×fps={round(product)}",
        )
    if is_num(last) and is_int(count):
        if abs(last - (count - 1) / fps) > _TS_TOL:
            out.err(
                "LAST_TIMESTAMP",
                "manifest",
                "$.sampling.last_timestamp_s",
                f"last_timestamp_s 應為 (count−1)/fps={(count - 1) / fps}；它不是 duration_s",
            )
        if last == duration:
            out.err(
                "LAST_TIMESTAMP_IS_DURATION",
                "manifest",
                "$.sampling",
                "last_timestamp_s 不得當成 duration_s（半開區間的終點沒有對應的影格）",
            )


@rule(
    "RUN-003",
    "manifest.allowlist 的 file_sha256 等於實際提供的 safe 檔位元組 hash",
    "契約 §2.1（file_sha256）、§3.10 allowlist",
    "contract",
)
def run_allowlist_hashes(ctx: Context, out: Collector) -> None:
    if not ctx.file_sha256:
        raise Skip("以記憶體文件驗證，沒有檔案位元組可核對")
    allowlist = (ctx.manifest or {}).get("allowlist")
    if not isinstance(allowlist, list):
        return
    entries = {item.get("role"): item for item in allowlist if isinstance(item, dict)}
    for role in ("scene_static", "cameras", "rgb_index", "runtime_profile"):
        actual = ctx.file_sha256.get(role)
        if actual is None:
            continue
        entry = entries.get(role)
        if entry is None:
            out.err(
                "ALLOWLIST_ROLE_MISSING", "manifest", "$.allowlist", f"allowlist 沒有列出 {role}"
            )
            continue
        if entry.get("filename") != SAFE_FILENAMES[role]:
            out.err(
                "ALLOWLIST_FILENAME",
                "manifest",
                "$.allowlist",
                f"{role} 的 filename 應為 {SAFE_FILENAMES[role]}",
            )
        if entry.get("file_sha256") != actual:
            out.err(
                "FILE_HASH_MISMATCH",
                "manifest",
                "$.allowlist",
                f"{role} 的 file_sha256 與實際檔案不符（完整性錯誤，整個 run fail closed）",
            )


def _run_cameras(ctx: Context) -> list[str]:
    run_id = (ctx.manifest or {}).get("run_id")
    bound = [
        c
        for b in ctx.run_bindings
        if b.get("run_id") == run_id and isinstance(c := b.get("camera_id"), str)
    ]
    if bound:
        return sorted(set(bound))
    index = ctx.rgb_index or {}
    seen = {
        i.get("camera_id")
        for k in ("records", "missing")
        for i in (index.get(k) or [])
        if isinstance(i, dict)
    }
    return sorted(c for c in seen if isinstance(c, str))


@rule(
    "RUN-004",
    "rgb_index：每個 expected sample 正好出現在 records[] 或 missing[] 一處；時間戳與 rgb_ref 正確",
    "契約 v1.1 §2.3、§3.11（RGB_INDEX_INCOMPLETE；v1.0 @2643771 無此結構）",
)
def run_rgb_grid(ctx: Context, out: Collector) -> None:
    index = ctx.rgb_index
    if not isinstance(index, dict):
        return
    if _is_preview(ctx):
        raise Skip(
            "preview run（purpose=CALIBRATION_PREVIEW 或 complete=false）：index 結構未定（U12）"
        )
    s = _sampling(ctx)
    count, fps = s.get("sample_count_per_camera"), s.get("fps")
    if not (is_int(count) and is_num(fps) and fps > 0):
        return
    cameras = set(_run_cameras(ctx))
    seen: dict[tuple[str, int], list[str]] = {}
    refs: dict[str, int] = {}
    for kind in ("records", "missing"):
        for i, item in enumerate(index.get(kind) or []):
            if not isinstance(item, dict):
                continue
            cam, idx, ts = item.get("camera_id"), item.get("frame_index"), item.get("timestamp_s")
            path = f"$.{kind}[{i}]"
            if not isinstance(cam, str) or not is_int(idx):
                continue
            if cam not in cameras:
                out.err(
                    "RGB_INDEX_UNKNOWN_CAMERA",
                    "rgb_index",
                    f"{path}.camera_id",
                    f"camera_id 不屬於這個 run 的鏡頭 {sorted(cameras)}",
                    cam,
                )
                continue
            if not 0 <= idx < count:
                out.err(
                    "RGB_INDEX_OUT_OF_RANGE",
                    "rgb_index",
                    f"{path}.frame_index",
                    f"frame_index 超出 [0, {count})（OUT_OF_RANGE）",
                    cam,
                )
                continue
            seen.setdefault((cam, idx), []).append(kind)
            if is_num(ts) and abs(ts - idx / fps) > _TS_TOL:
                out.err(
                    "RGB_INDEX_TIMESTAMP",
                    "rgb_index",
                    f"{path}.timestamp_s",
                    f"timestamp_s 應為 frame_index/fps={idx / fps}",
                    cam,
                )
            if kind == "records":
                ref = item.get("rgb_ref")
                match = RGB_REF_PATTERN.match(ref) if isinstance(ref, str) else None
                if match is None or match["camera"] != cam or int(match["index"]) != idx:
                    out.err(
                        "RGB_REF_FORMAT",
                        "rgb_index",
                        f"{path}.rgb_ref",
                        "rgb_ref 必須是 rgb/<CAM_ID>/frame_<frame_index:06d>.png 的相對路徑，"
                        "且與 camera_id／frame_index 一致",
                        cam,
                    )
                elif ref in refs:
                    out.err(
                        "RGB_REF_DUPLICATE", "rgb_index", f"{path}.rgb_ref", "rgb_ref 重複", cam
                    )
                else:
                    refs[str(ref)] = idx
    for cam in sorted(cameras):
        for idx in range(count):
            where = seen.get((cam, idx), [])
            if not where:
                out.err(
                    "RGB_INDEX_INCOMPLETE",
                    "rgb_index",
                    "$",
                    f"sample {idx} 既不在 records[] 也不在 missing[]（RGB_INDEX_INCOMPLETE，整個 "
                    "run fail closed）",
                    cam,
                )
            elif len(where) > 1:
                out.err(
                    "RGB_INDEX_DUPLICATE",
                    "rgb_index",
                    "$",
                    f"sample {idx} 出現 {len(where)} 次（{', '.join(where)}）；必須正好一處",
                    cam,
                )


@rule(
    "RUN-005",
    "事件規格與設計稿一致：鏡頭組、sample 數、解析度、幀率、格式",
    "契約 §5.0、§5.2、§5.3；設計稿 §3",
    "design",
)
def run_event_design(ctx: Context, out: Collector) -> None:
    design = ctx.design
    manifest = ctx.manifest
    if design is None or not isinstance(manifest, dict):
        raise Skip("沒有 design_reference 或 manifest")
    run_id = manifest.get("run_id")
    match = RUN_ID_PATTERN.match(run_id) if isinstance(run_id, str) else None
    if match is None:
        raise Skip("run_id 不是事件 run（preview 或格式錯誤，見 RUN-001）")
    events = design["events"]
    event = events["items"].get(match["event"])
    if event is None:
        raise Skip(f"事件 {match['event']} 沒有設計稿規格（B2 另寫規格）")
    s, base = _sampling(ctx), events["sampling"]
    if match["sampling"] + "-v" + match["sv"] != base["sampling_version"]:
        out.err(
            "SAMPLING_VERSION",
            "manifest",
            "$.run_id",
            f"第一版取樣為 {base['sampling_version']}（D25）",
        )
    for key in ("fps", "image_size_px", "format", "sampling_version"):
        if key in s and s[key] != base[key]:
            out.err(
                "SAMPLING_MISMATCH",
                "manifest",
                f"$.sampling.{key}",
                f"{key} 應為 {base[key]!r}（D25），實際 {s[key]!r}",
            )
    for key in ("duration_s", "sample_count_per_camera"):
        if key in s and s[key] != event[key]:
            out.err(
                "EVENT_SAMPLING_MISMATCH",
                "manifest",
                f"$.sampling.{key}",
                f"事件 {match['event'].upper()} 的 {key} 應為 {event[key]}",
            )
    if "last_timestamp_s" in s and (
        not is_num(s["last_timestamp_s"])
        or abs(s["last_timestamp_s"] - event["last_timestamp_s"]) > _TS_TOL
    ):
        out.err(
            "EVENT_SAMPLING_MISMATCH",
            "manifest",
            "$.sampling.last_timestamp_s",
            f"last_timestamp_s 應為 {event['last_timestamp_s']}",
        )
    if _run_cameras(ctx) != sorted(event["cameras"]):
        out.err(
            "EVENT_CAMERAS",
            "manifest",
            "$",
            f"事件 {match['event'].upper()} 渲染的鏡頭應為 {sorted(event['cameras'])}（事件 A "
            "不含 CAM_N1）",
        )
    total = len(event["cameras"]) * event["sample_count_per_camera"]
    records = len((ctx.rgb_index or {}).get("records") or []) + len(
        (ctx.rgb_index or {}).get("missing") or []
    )
    if ctx.rgb_index and not _is_preview(ctx) and records != total:
        out.err(
            "EVENT_FRAME_TOTAL",
            "rgb_index",
            "$",
            f"records＋missing 應共 {total} 筆（鏡頭數×sample 數），實際 {records}",
        )
