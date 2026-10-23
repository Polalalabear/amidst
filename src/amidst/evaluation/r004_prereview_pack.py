"""Portable, evidence-pinned static pre-review bundles; never grant approval.

This is not a detector evaluation importer. Human reviews remain advisory and
cannot mutate graph permissions, parameter files, or formal evaluation labels.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import struct
import tempfile
import zlib
from datetime import date
from pathlib import Path, PurePosixPath

COLUMNS = [
    "item_id",
    "category",
    "object_id",
    "image_refs",
    "statement",
    "decision",
    "reason",
    "reviewer",
    "date",
]
FIXED_COLUMNS = COLUMNS[:5]
EDITABLE_COLUMNS = COLUMNS[5:]
DECISIONS = {"T", "F", "不確定"}
COPY_ROLES = {
    "region_graph",
    "camera_graph",
    "roi_mapping",
    "region_meshes",
    "camera_catalog",
    "hsv_report",
    "hsv_config",
}
PNG = b"\x89PNG\r\n\x1a\n"
NOTICE = (
    "前置靜態審查／HSV PREVIEW；不是正式 detector T/F 評估。"
    "T 只記錄組員意見，不核准 G4/G6、物理通行、自動切鏡或辨識正確率。"
)


class PackError(ValueError):
    """A trust, source, schema, or filesystem check failed closed."""


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _no_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise PackError("SYMLINK_REJECTED")
    return path


def _read(path):
    path = _no_symlinks(path)
    if not path.is_file():
        raise PackError("REGULAR_FILE_REQUIRED")
    return path.read_bytes()


def _pinned(path, digest):
    raw = _read(path)
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or sha(raw) != digest
    ):
        raise PackError("SHA256_MISMATCH")
    return raw


def _json(raw):
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise PackError("INVALID_JSON") from exc


def _relative(value):
    if not isinstance(value, str) or "\\" in value or "|" in value or ":" in value:
        raise PackError("UNSAFE_RELATIVE_PATH")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or str(path) != value or ".." in path.parts:
        raise PackError("UNSAFE_RELATIVE_PATH")
    return value


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise PackError("UNSAFE_IDENTIFIER")
    return value


def formula_risk(value):
    return isinstance(value, str) and (
        value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))
    )


def csv_safe(value):
    value = str(value)
    return "'" + value if formula_risk(value) or value.startswith("'") else value


def decode_editable(value):
    """Reverse exactly our apostrophe escape, preserving ordinary apostrophes."""
    if value.startswith("''"):
        return value[1:]
    if value.startswith("'") and formula_risk(value[1:]):
        return value[1:]
    if formula_risk(value):
        raise PackError("CSV_FORMULA_NOT_NEUTRALIZED")
    return value


def _csv(rows, columns=COLUMNS):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def _parse_csv(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        return reader.fieldnames, list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise PackError("INVALID_UTF8_CSV") from exc


def _disk(path):
    if shutil.disk_usage(path).free < 8 * 1024**3:
        raise PackError("DISK_BELOW_8_GIB")


def _sanitize(value):
    """Remove machine-specific absolute paths from portable presentation data."""
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str) and (
        "/Users/" in value
        or "/private/" in value
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:[\\/]", value)
    ):
        return "LOCAL_SOURCE_NOT_DISTRIBUTED"
    return value


def sanitize_png(raw):
    """Validate bounded scanlines, then strip metadata without re-encoding.

    Every source chunk CRC is checked. IHDR and concatenated IDAT bytes remain
    identical; source files are never written. Only non-interlaced 8-bit gray,
    gray-alpha, RGB and RGBA are accepted, at most 4096 per dimension and 64 MiB
    inflated scanline bytes. No visibility, object, or geometric claim is made.
    """
    if not raw.startswith(PNG):
        raise PackError("PNG_HEADER_INVALID")
    offset, chunks, ihdr, idat, removed, ended = 8, [], None, [], [], False
    width = height = channels = 0
    idat_closed = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise PackError("PNG_TRUNCATED")
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        end = offset + length + 12
        if end > len(raw):
            raise PackError("PNG_TRUNCATED")
        kind = raw[offset + 4 : offset + 8]
        if not re.fullmatch(b"[A-Za-z]{4}", kind):
            raise PackError("PNG_CHUNK_TYPE_INVALID")
        content = raw[offset + 8 : end - 4]
        expected = struct.unpack(">I", raw[end - 4 : end])[0]
        if zlib.crc32(kind + content) & 0xFFFFFFFF != expected:
            raise PackError("PNG_CRC_INVALID")
        if ihdr is None and kind != b"IHDR":
            raise PackError("PNG_IHDR_REQUIRED_FIRST")
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise PackError("PNG_IHDR_INVALID")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", content
            )
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color, 0)
            if not 1 <= width <= 4096 or not 1 <= height <= 4096:
                raise PackError("PNG_DIMENSION_LIMIT")
            if depth != 8 or not channels or compression != 0 or filtering != 0 or interlace != 0:
                raise PackError("PNG_MODE_UNSUPPORTED")
            if height * (width * channels + 1) > 64 * 1024**2:
                raise PackError("PNG_DECODED_SIZE_LIMIT")
            ihdr = content
        if kind == b"IDAT":
            if idat_closed:
                raise PackError("PNG_IDAT_NOT_CONSECUTIVE")
            idat.append(content)
        elif idat:
            idat_closed = True
        if kind in {b"tEXt", b"iTXt", b"zTXt", b"eXIf"}:
            removed.append(kind.decode("ascii"))
        else:
            chunks.append(raw[offset:end])
        offset = end
        if kind == b"IEND":
            if length != 0 or offset != len(raw):
                raise PackError("PNG_IEND_INVALID")
            ended = True
            break
    if not ended or ihdr is None or not idat:
        raise PackError("PNG_REQUIRED_CHUNK_MISSING")
    compressed = b"".join(idat)
    scanline_size = width * channels + 1
    expected_size = height * scanline_size
    decoder = zlib.decompressobj()
    try:
        # One byte over the exact bound detects oversized streams while never
        # expanding an attacker-controlled stream without a fixed output cap.
        decoded = decoder.decompress(compressed, expected_size + 1)
    except zlib.error as exc:
        raise PackError("PNG_ZLIB_INVALID") from exc
    if (
        len(decoded) != expected_size
        or not decoder.eof
        or decoder.unconsumed_tail
        or decoder.unused_data
    ):
        raise PackError("PNG_ZLIB_SIZE_OR_STREAM_INVALID")
    if any(decoded[row * scanline_size] > 4 for row in range(height)):
        raise PackError("PNG_SCANLINE_FILTER_INVALID")
    exported = PNG + b"".join(chunks)
    return exported, {
        "source_sha256": sha(raw),
        "exported_sha256": sha(exported),
        "ihdr_sha256": sha(ihdr),
        "idat_sha256": sha(b"".join(idat)),
        "pixel_data_sha256": sha(ihdr + b"".join(idat)),
        "removed_metadata_chunks": removed,
        "pixel_encoding_preserved": True,
        "scanline_validation": "BOUNDED_ZLIB_RGB_RGBA_GRAY_GRAYALPHA_8BIT_NONINTERLACED",
        "width": width,
        "height": height,
        "inflated_scanline_bytes": expected_size,
    }


def _item(item_id, category, object_id, image_refs, statement, **details):
    for ref in image_refs:
        _relative(ref)
    return {
        "item_id": _identifier(item_id),
        "category": csv_safe(category),
        "object_id": csv_safe(object_id),
        "image_refs": image_refs,
        "statement": csv_safe(statement),
        **_sanitize(details),
    }


def _make_items(config, documents, report):
    items = []
    cameras = sorted(config["static_frames"])
    for camera in cameras:
        refs = [f"images/static/{camera}.png", f"images/exits/{camera}.png"]
        items.append(
            _item(
                f"CAM_{camera}",
                "CAMERA_IDENTITY",
                camera,
                refs,
                f"這組原圖與橘色出口圖對應 {camera}，且標示不妨礙核對。",
            )
        )
        items.append(
            _item(
                f"ROI_{camera}",
                "EXIT_ROI",
                camera,
                refs,
                f"{camera} 橘色多邊形可作為可見地面的出口接近區域提案。",
                context="僅審靜態合理性；不能證明門檻、通行、覆蓋完整或人物路線。",
            )
        )
    for edge in documents["region_graph"]["edges"]:
        eid = _identifier(edge["edge_id"])
        items.append(
            _item(
                f"EDGE_{eid}",
                "REGION_EDGE",
                eid,
                ["images/region_map.svg"],
                f"區域連結提案 {eid}（{' ↔ '.join(edge['regions'])}）的靜態依據足夠供前置審查。",
                details=edge,
                context="沒有足夠依據請填不確定並寫缺少什麼；T 不核准物理通行。",
            )
        )
    for transition in documents["camera_graph"]["transitions"]:
        tid = _identifier(transition["transition_id"])
        source, target = transition["from_camera_id"], transition["to_camera_id"]
        if source not in cameras or target not in cameras:
            raise PackError("TRANSITION_CAMERA_MISSING")
        refs = [
            "images/region_map.svg",
            f"images/exits/{source}.png",
            f"images/static/{target}.png",
        ]
        items.append(
            _item(
                f"PATH_{tid}",
                "CAMERA_TRANSITION",
                tid,
                refs,
                f"{source} → {target} 的候選連通提案與所列區域／出口依據相符。",
                details=transition,
                context="T 不代表目標必經、相機重疊已測或可自動切鏡。",
            )
        )
    for index, unresolved in enumerate(report.get("unresolved", []), 1):
        uid = str(unresolved.get("id", f"gap_{index:03d}"))
        items.append(
            _item(
                f"GAP_{index:03d}",
                "UNRESOLVED",
                uid,
                ["images/region_map.svg"],
                "我已檢視此缺口與所列證據，並在原因寫明可接受／需修改／資料不足。",
                context=unresolved.get("summary", "資料不足"),
                details=unresolved,
            )
        )
    rows = documents["hsv_report"].get("rows", [])
    if len(rows) != 35:
        raise PackError("HSV_REQUIRES_35_ROWS")
    for index, row in enumerate(rows, 1):
        cid = f"crop_{index:03d}"
        for color, chinese in [("red", "紅"), ("blue", "藍")]:
            verdict = row.get("summary", {}).get("verdicts", {}).get(color)
            if verdict not in {"STRONG", "WEAK", "NONE", "UNKNOWN"}:
                raise PackError("HSV_VERDICT_INVALID")
            if verdict == "NONE":
                claim = f"這張上半身裁切沒有可辨認的{chinese}色衣物。"
            elif verdict in {"STRONG", "WEAK"}:
                claim = f"這張上半身裁切有可辨認的{chinese}色衣物。"
            else:
                claim = f"這張上半身裁切不足以判斷是否有{chinese}色衣物。"
            items.append(
                _item(
                    f"HSV_{index:03d}_{color.upper()}",
                    f"HSV_{color.upper()}",
                    cid,
                    [f"images/hsv/{cid}.png"],
                    claim,
                    context=f"系統 verdict={verdict}；PREVIEW，沒有人工正確率。圖不足請填不確定。",
                    system_verdict=verdict,
                    color=color,
                    rgb_ref=row.get("rgb_ref"),
                    detector_ordinal=row.get("detector_ordinal"),
                )
            )
    return items


def _render_map(config_path, config_sha256):
    helper_path = Path(__file__).with_name("q1q5_graph_check.py")
    spec = importlib.util.spec_from_file_location("r004_static_graph_check", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    try:
        return helper.render_static_map(config_path, config_sha256).encode("utf-8")
    except (helper.GraphCheckError, KeyError, ValueError, TypeError) as exc:
        raise PackError("STATIC_MAP_FAILED: " + str(exc)) from exc


def build_pack(config_path, config_sha256, report_path, report_sha256, output_dir, ui_assets=None):
    """Build a new immutable pack plus separate blank, editable return copies."""
    config = _json(_pinned(config_path, config_sha256))
    report_raw = _pinned(report_path, report_sha256)
    report = _json(report_raw)
    if config.get("schema_version") != "q-demo.r004-prereview-inputs.v1":
        raise PackError("INPUT_SCHEMA_INVALID")
    if (
        report.get("schema_version") != "q-demo.r004-prereview-check.v1"
        or report.get("status") != "REVIEW_REQUIRED"
    ):
        raise PackError("REPORT_SCHEMA_OR_STATUS_INVALID")
    report_body = {k: v for k, v in report.items() if k != "output_sha256"}
    if report.get("output_sha256") != sha(canonical(report_body)):
        raise PackError("REPORT_CONTENT_HASH_INVALID")
    if report.get("config_sha256") != config_sha256:
        raise PackError("REPORT_CONFIG_BINDING_MISMATCH")
    if len(config.get("static_frames", {})) != 8 or set(config["static_frames"]) != set(
        config.get("overlay_frames", {})
    ):
        raise PackError("EIGHT_CAMERA_FRAME_PAIRS_REQUIRED")
    if set(config.get("hsv_crops", {})) != {f"crop_{i:03d}" for i in range(1, 36)}:
        raise PackError("THIRTY_FIVE_CROPS_REQUIRED")
    # Verify every pin, including the intentionally undistributed static geometry.
    sources, documents = {}, {}
    for role, ref in config["files"].items():
        _identifier(role)
        raw = _pinned(ref["path"], ref["sha256"])
        sources[role] = raw
        documents[role] = _json(raw)
    if not COPY_ROLES <= sources.keys():
        raise PackError("SOURCE_ROLE_MISSING")
    if (
        len(documents["region_graph"].get("edges", [])) != 6
        or len(documents["camera_graph"].get("transitions", [])) != 17
    ):
        raise PackError("R004_REQUIRES_SIX_EDGES_AND_SEVENTEEN_TRANSITIONS")
    images, media_exports = {}, {}
    for group, dest in [
        ("static_frames", "static"),
        ("overlay_frames", "exits"),
        ("hsv_crops", "hsv"),
    ]:
        for name, ref in config[group].items():
            _identifier(name)
            raw = _pinned(ref["path"], ref["sha256"])
            exported, media_receipt = sanitize_png(raw)
            relative = f"images/{dest}/{name}.png"
            images[relative] = exported
            media_exports[relative] = media_receipt
    items = _make_items(config, documents, report)
    if len({item["item_id"] for item in items}) != len(items):
        raise PackError("DUPLICATE_ITEM_ID")
    output = _no_symlinks(output_dir)
    if output.exists():
        raise PackError("OUTPUT_ALREADY_EXISTS")
    if not output.parent.is_dir():
        raise PackError("OUTPUT_PARENT_MISSING")
    _disk(output.parent)
    assets = (
        Path(ui_assets)
        if ui_assets
        else Path(__file__).resolve().parents[3] / "scripts/r004_prereview_ui"
    )
    asset_data = {
        dest: _read(assets / name)
        for name, dest in [
            ("index.html", "START_HERE.html"),
            ("app.js", "app.js"),
            ("style.css", "style.css"),
        ]
    }
    asset_data["images/region_map.svg"] = _render_map(config_path, config_sha256)
    data = {
        "schema_version": "q-demo.r004-prereview-data.v1",
        "title": "r004 前置靜態審查包",
        "notice": NOTICE,
        "columns": COLUMNS,
        "source_heads": config.get("source_heads", {}),
        "source_pins": {role: ref["sha256"] for role, ref in config["files"].items()},
        "report": _sanitize(report),
        "media_exports": media_exports,
        "summary": _sanitize(report.get("counts", {})),
        "known_gaps": _sanitize(report.get("unresolved", [])),
        "items": items,
        "scope": {
            "evaluation_eligible": False,
            "human_approval": False,
            "event_rgb_included": False,
            "gt_included": False,
            "formal_detector_tf": False,
        },
    }
    csv_rows = [
        {
            **{k: ("|".join(item[k]) if k == "image_refs" else item[k]) for k in FIXED_COLUMNS},
            **{k: "" for k in EDITABLE_COLUMNS},
        }
        for item in items
    ]
    template = _csv(csv_rows)
    owner_columns = ["gate", "suggestion", "owner_decision", "reason", "reviewer", "date"]
    owner_rows = [
        {"gate": gate, "suggestion": "由指定核定者另行記錄；此表不是可執行核准"}
        for gate in ["G4_ALLOWED_PURPOSES_AND_PATHS", "G6_HSV_PARAMETERS"]
    ]
    payloads = {
        **images,
        **asset_data,
        **{f"provenance/{role}.json": sources[role] for role in sorted(COPY_ROLES)},
        "provenance/engineering_report.json": canonical(_sanitize(report)) + b"\n",
        "provenance/media_exports.json": canonical(media_exports) + b"\n",
        "DATA.json": canonical(data) + b"\n",
        "data.js": b"window.R004_REVIEW_DATA=" + canonical(data) + b";\n",
        "templates/審查表.csv": template,
        "templates/OWNER_DECISIONS.csv": _csv(owner_rows, owner_columns),
        "tools/r004_prereview_pack.py": _read(__file__),
        "tools/verify_bundle.py": (
            b"import argparse, json\n"
            b"from pathlib import Path\n"
            b"from r004_prereview_pack import verify_pack, import_pack, PackError\n"
            b"p=argparse.ArgumentParser()\n"
            b"p.add_argument('--manifest-sha256',required=True)\n"
            b"p.add_argument('--returned-csv')\n"
            b"a=p.parse_args()\n"
            b"root=Path(__file__).resolve().parents[1]\n"
            b"try:\n"
            b" if a.returned_csv:\n"
            b"  r=import_pack(root,a.manifest_sha256,a.returned_csv)\n"
            b" else:\n"
            b"  m,rows=verify_pack(root,a.manifest_sha256)\n"
            b"  r={'status':'VERIFIED','items':len(rows),'approval_granted':False}\n"
            b" print(json.dumps(r,ensure_ascii=False))\n"
            b"except (PackError,OSError,ValueError,KeyError) as e:\n"
            b" print(json.dumps({'status':'INVALID','error':str(e)}))\n"
            b" raise SystemExit(1)\n"
        ),
        "README.txt": (
            "r004 前置靜態審查包：操作步驟\n\n1. 先完整解壓縮資料"
            "夾；用 Edge／Chrome／Firefox 開 STAR"
            "T_HERE.html。Windows/macOS 可離線操"
            "作，不需模型、Git、Python 或登入。\n2. 填審查者"
            "姓名與 YYYY-MM-DD 日期。每位審查者使用自己的一份"
            " CSV；不要代簽其他人的意見。\n3. 建議按分類分工：一般"
            "組員先看鏡頭對應、出口與紅／藍 PREVIEW；熟悉空間配置"
            "者再看區域邊及相機轉移；待決缺口由相關負責人逐項說明。各分類"
            "均保留全部列，非本人負責項目可空白，回收會列為 INCOMP"
            "LETE。\n4. 對同編號說法填 T=圖片／靜態證據支持、F"
            "=反駁、不確定=資訊不足；不要猜答案。F／不確定必填原因；待"
            "決缺口 UNRESOLVED 無論填哪一項都必填原因，說明可"
            "接受／需修改／資料不足。一般 T 可補充備註；未填項不是 F"
            "。\n5. HSV 的 STRONG／WEAK／NONE／UN"
            "KNOWN 是系統既有啟發式判定。WEAK 不是確定有；看不"
            "清衣物就選不確定。此批為 PREVIEW，不是正式 dete"
            "ctor T/F，不能當辨識正確率。\n6. 隨時按『匯出 C"
            "SV』保存。檔案通常在瀏覽器的下載資料夾（Downloads"
            "），若瀏覽器詢問位置就自行選擇；匯出不會直接覆寫本包原檔。把"
            "下載檔移到 RETURN/，檔名建議 審查表_姓名_YYYY"
            "-MM-DD.csv，保留之前版本。\n7. 要續填時重新開頁"
            "面，按匯入 CSV 選上一份下載檔，再繼續填；只靠目前頁面暫"
            "存不算交件，關頁前先匯出。也可用 UTF-8 CSV 編輯 "
            "RETURN/審查表.csv，但只改 decision、re"
            "ason、reviewer、date 四欄。\n8. 將整包資"
            "料夾（可壓成 ZIP）及填寫 CSV 一起交回使用者，並告知"
            "負責分類與未完成項目。不要改 templates、圖檔、DA"
            "TA、MANIFEST 或固定欄位；RETURN 的新 ha"
            "sh 另記，不要求與空白模板整檔 hash 相同。\n\n驗收限"
            "制：此版已跑程式／CSV測試，尚未完成 Windows 或真"
            "瀏覽器離線驗收；首次打開請先確認圖片、填答、匯出與續填可用。"
            "\n\n前置靜態審查／HSV PREVIEW；不是正式 dete"
            "ctor T/F 評估。T 只記錄組員意見，不核准 G4/G"
            "6、物理通行、自動切鏡或辨識正確率。\n待決缺口 T 只表示已"
            "檢視並說明，不代表缺少證據已補齊。OWNER_DECISIO"
            "NS.csv 僅供權責者另填建議，不會寫回任何輸入或解除 g"
            "ate。\n"
        ).encode(),
    }
    manifest = {
        "schema_version": "q-demo.r004-prereview-manifest.v1",
        "evaluation_eligible": False,
        "human_approval": False,
        "config_sha256": config_sha256,
        "report_sha256": report_sha256,
        "item_count": len(items),
        "columns": COLUMNS,
        "locked_columns": FIXED_COLUMNS,
        "editable_files": ["RETURN/審查表.csv", "RETURN/OWNER_DECISIONS.csv"],
        "files": {name: sha(raw) for name, raw in sorted(payloads.items())},
    }
    manifest_raw = canonical(manifest) + b"\n"
    staging = Path(tempfile.mkdtemp(prefix=".r004-prereview-", dir=output.parent))
    try:
        for name, raw in {
            **payloads,
            "MANIFEST.json": manifest_raw,
            "RETURN/審查表.csv": template,
            "RETURN/OWNER_DECISIONS.csv": payloads["templates/OWNER_DECISIONS.csv"],
        }.items():
            _disk(staging)
            target = staging / _relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        if output.exists():
            raise PackError("OUTPUT_ALREADY_EXISTS")
        os.rename(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {
        "schema_version": "q-demo.r004-prereview-build.v1",
        "status": "REVIEW_REQUIRED",
        "output_dir": str(output),
        "manifest_sha256": sha(manifest_raw),
        "item_count": len(items),
        "immutable_file_count": len(payloads),
        "approval_granted": False,
        "evaluation_eligible": False,
    }


def verify_pack(pack_dir, manifest_sha256):
    pack = _no_symlinks(pack_dir)
    manifest = _json(_pinned(pack / "MANIFEST.json", manifest_sha256))
    if (
        manifest.get("schema_version") != "q-demo.r004-prereview-manifest.v1"
        or manifest.get("columns") != COLUMNS
    ):
        raise PackError("MANIFEST_SCHEMA_INVALID")
    for name, digest in manifest["files"].items():
        _pinned(pack / _relative(name), digest)
    if (
        manifest.get("evaluation_eligible") is not False
        or manifest.get("human_approval") is not False
    ):
        raise PackError("APPROVAL_OR_EVALUATION_ESCALATION_REJECTED")
    header, rows = _parse_csv(_read(pack / "templates/審查表.csv"))
    if (
        header != COLUMNS
        or len({r["item_id"] for r in rows}) != len(rows)
        or len(rows) != manifest["item_count"]
    ):
        raise PackError("TEMPLATE_SCHEMA_INVALID")
    return manifest, rows


def import_pack(pack_dir, manifest_sha256, returned_csv=None, output_dir=None):
    """Validate a human return without deriving answers or granting approval."""
    manifest, template = verify_pack(pack_dir, manifest_sha256)
    returned_path = Path(returned_csv) if returned_csv else Path(pack_dir) / "RETURN/審查表.csv"
    raw = _read(returned_path)
    errors, incomplete, results = [], [], []
    try:
        header, rows = _parse_csv(raw)
    except PackError as exc:
        header, rows = [], []
        errors.append({"row": None, "reason": str(exc)})
    if header != COLUMNS:
        errors.append({"row": 1, "reason": "CSV_COLUMNS_INVALID"})
    originals = {row["item_id"]: row for row in template}
    seen = set()
    for line, row in enumerate(rows, 2):
        rid = row.get("item_id")
        row_errors, missing = [], []
        if rid not in originals:
            row_errors.append("UNKNOWN_ITEM_ID")
        elif rid in seen:
            row_errors.append("DUPLICATE_ITEM_ID")
        seen.add(rid)
        if None in row or any(row.get(col) is None for col in COLUMNS):
            row_errors.append("CSV_ROW_WIDTH_INVALID")
        if rid in originals and any(row.get(col) != originals[rid][col] for col in FIXED_COLUMNS):
            row_errors.append("FIXED_COLUMN_CHANGED")
        decoded = {}
        for col in EDITABLE_COLUMNS:
            try:
                decoded[col] = decode_editable(row.get(col) or "")
            except PackError as exc:
                row_errors.append(str(exc))
                decoded[col] = ""
        decision = decoded.get("decision", "")
        if decision and decision not in DECISIONS:
            row_errors.append("DECISION_INVALID")
        required = ["decision", "reviewer", "date"]
        if decision in {"F", "不確定"} or (
            rid in originals and originals[rid]["category"] == "UNRESOLVED" and decision
        ):
            required.append("reason")
        for col in required:
            if not decoded.get(col, "").strip():
                missing.append(col)
        entered_date = decoded.get("date", "")
        if entered_date:
            try:
                if date.fromisoformat(entered_date).isoformat() != entered_date:
                    raise ValueError()
            except ValueError:
                row_errors.append("DATE_MUST_BE_YYYY_MM_DD")
        if row_errors:
            errors.append({"row": line, "item_id": rid, "reasons": row_errors})
        elif missing:
            incomplete.append({"row": line, "item_id": rid, "missing": missing})
        results.append(
            {
                "item_id": rid,
                **decoded,
                "status": "INVALID" if row_errors else "INCOMPLETE" if missing else "VALID",
            }
        )
    for rid in sorted(set(originals) - seen):
        errors.append({"item_id": rid, "reason": "MISSING_ITEM_ID"})
    status = "INVALID" if errors else "INCOMPLETE" if incomplete else "VALID"
    receipt = {
        "schema_version": "q-demo.r004-prereview-import.v1",
        "status": status,
        "pack_manifest_sha256": manifest_sha256,
        "returned_csv_sha256": sha(raw),
        "template_csv_sha256": manifest["files"]["templates/審查表.csv"],
        "counts": {
            "expected": len(template),
            "received": len(rows),
            "valid": sum(r["status"] == "VALID" for r in results),
            "incomplete": len(incomplete),
            "invalid_errors": len(errors),
        },
        "errors": errors,
        "incomplete": incomplete,
        "rows": results,
        "approval_granted": False,
        "evaluation_eligible": False,
        "input_files_modified": False,
    }
    receipt["output_sha256"] = sha(canonical(receipt))
    if output_dir is not None:
        output = _no_symlinks(output_dir)
        if output.exists():
            raise PackError("OUTPUT_ALREADY_EXISTS")
        _disk(output.parent)
        output.mkdir()
        (output / "receipt.json").write_bytes(canonical(receipt) + b"\n")
        # Raw CSV is preserved as evidence only; never re-export it unsanitized.
        (output / "returned.csv.raw.txt").write_bytes(raw)
    return receipt
