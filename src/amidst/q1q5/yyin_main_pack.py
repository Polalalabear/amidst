"""CQ-27: deterministic authoring-pack framework; no answers or release authority.

This module is used by the offline builder, never by inference. Source files are
read only. The existing team-review-pack.v1 manifest and importer stay unchanged.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import struct
import zipfile

ASSETS = Path(__file__).with_name("yyin_main_pack_assets")
CAMERAS = ("CAM_BRANCH", "CAM_ENTRY", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_R101_IN", "CAM_W1", "CAM_W2", "CAM_WIDE")
PINS = {
    "clock": "a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a",
    "run": "2f9c77fac097098787a1b23602cc59868677d655a1c4f92c0831c21f9dd0a0b9",
    "catalog_receipt": "3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5",
    "object_list": "a8d349cf2d03676f941aee9bc91e8518b352221f12b45b67634ae2aec26c5776",
}
SOURCE_MANIFEST = "531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4"
CATALOG = "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f"
TEXT_FILE = "A_文字情境/情境.csv"
REVIEW_FILE = "B_畫面審查/審查表.csv"


class PackError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(doc):
    return json.dumps(doc, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def load(raw):
    def pairs(values):
        result = {}
        for k, v in values:
            require(k not in result, "DUPLICATE_JSON_KEY")
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, "NONFINITE_JSON"))


def regular(path):
    path = Path(path).absolute()
    require(path.resolve() == path and path.is_file(), "REGULAR_CANONICAL_FILE_REQUIRED")
    return path


def csv_bytes(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def public_text(raw):
    text = raw.decode("utf-8-sig")
    require(not re.search(r"/Users/|/private/|[A-Za-z]:\\|t_X|t_N|評分窗|劇本|\bGT\b|\.blend\b|renderer|trajectory|visibility|depth", text, re.I),
            "PRIVATE_OR_EVALUATION_TEXT_FORBIDDEN")


def png(raw):
    require(raw.startswith(b"\x89PNG\r\n\x1a\n"), "PNG_REQUIRED")
    pos = 8
    tags = []
    while pos < len(raw):
        require(pos + 12 <= len(raw), "PNG_TRUNCATED")
        size = struct.unpack(">I", raw[pos:pos + 4])[0]
        tag = raw[pos + 4:pos + 8]
        require(tag in {b"IHDR", b"IDAT", b"IEND", b"sRGB", b"gAMA", b"cHRM", b"oFFs", b"pHYs", b"PLTE", b"tRNS"},
                "PNG_METADATA_UNSELECTED")
        pos += size + 12
        require(pos <= len(raw), "PNG_TRUNCATED")
        tags.append(tag)
    require(tags and tags[0] == b"IHDR" and tags[-1] == b"IEND" and b"IDAT" in tags, "PNG_STRUCTURE_INVALID")


def inputs_from_files(config, synthetic_only):
    require(isinstance(config, dict) and set(config) == {"source_pack", *PINS}, "INPUT_CONFIG_FIELDS")
    source = config["source_pack"]
    require(isinstance(source, dict) and set(source) == {"path", "manifest_sha256"}, "SOURCE_PIN_REQUIRED")
    root = Path(source["path"]).absolute()
    require(root.resolve() == root and root.is_dir(), "SOURCE_ROOT_REQUIRED")
    raw_manifest = regular(root / "MANIFEST.json").read_bytes()
    require(sha(raw_manifest) == source["manifest_sha256"], "SOURCE_MANIFEST_PIN_MISMATCH")
    if not synthetic_only:
        require(sha(raw_manifest) == SOURCE_MANIFEST, "UNSELECTED_SOURCE_PACK")
    manifest = load(raw_manifest)
    docs, raw_pins, source_files = {}, {"source_manifest": sha(raw_manifest)}, {root / "MANIFEST.json": sha(raw_manifest)}
    for name, expected in PINS.items():
        ref = config[name]
        require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "INPUT_PIN_REQUIRED")
        path = regular(ref["path"])
        raw = path.read_bytes()
        require(sha(raw) == ref["sha256"] and (synthetic_only or sha(raw) == expected), "INPUT_PIN_MISMATCH: " + name)
        docs[name], raw_pins[name], source_files[path] = load(raw), sha(raw), sha(raw)
    clock, run, freeze, objects = (docs[n] for n in ("clock", "run", "catalog_receipt", "object_list"))
    require(clock["schema_version"] == "q-demo.clock-mapping.v1" and clock["mapping_kind"] == "DECLARED_DEMO_CLOCK"
            and clock["run_id"] == run["run_id"] and clock["clock_id"] == run["clock_id"]
            and clock["source_duration_us"] == run["source_duration_us"] == 50_000_000
            and clock["timezone"] == "Asia/Taipei" and clock["rate"] == 1 and clock["t0_us"] == 0,
            "RUN_CLOCK_BINDING_MISMATCH")
    require(run["clock_mapping_file_sha256"] == raw_pins["clock"] and run["clock_mapping_content_sha256"] == clock["content_sha256"]
            and clock["content_sha256"] == sha(canonical({k: v for k, v in clock.items() if k != "content_sha256"})),
            "CLOCK_CONTENT_BINDING_MISMATCH")
    require(run["camera_catalog_freeze_sha256"] == raw_pins["catalog_receipt"]
            and run["camera_catalog_sha256"] == freeze["catalog_sha256"]
            and freeze["source_manifest_file_sha256"] == source["manifest_sha256"]
            and freeze["camera_ids"] == list(CAMERAS), "CATALOG_BINDING_MISMATCH")
    catalog_path = regular(root / "provenance/camera_catalog.json")
    catalog_raw = catalog_path.read_bytes()
    require(sha(catalog_raw) == freeze["catalog_sha256"] == manifest["files"]["provenance/camera_catalog.json"], "CATALOG_PIN_MISMATCH")
    require(synthetic_only or sha(catalog_raw) == CATALOG, "CATALOG_NOT_D84")
    source_files[catalog_path] = sha(catalog_raw)
    require(objects["manifest_sha256"] == source["manifest_sha256"] and objects["provenance_sha256"]["camera_catalog.json"] == sha(catalog_raw),
            "OBJECT_LIST_BINDING_MISMATCH")
    checks = objects["camera_checks"]
    require(len(checks) == len(CAMERAS) and {c["camera_id"] for c in checks} == set(CAMERAS), "OBJECT_CAMERA_SET_MISMATCH")
    images, cameras = {}, []
    for row in sorted(checks, key=lambda r: r["camera_id"]):
        camera = row["camera_id"]
        name = "images/static/" + camera + ".png"
        require(row["static_image_ref"] == name and type(row["car_question_eligible"]) is bool, "STATIC_REFERENCE_MISMATCH")
        path = regular(root / name)
        raw = path.read_bytes()
        require(sha(raw) == row["static_image_sha256"] == manifest["files"][name], "IMAGE_PIN_MISMATCH")
        png(raw)
        images["images/cameras/" + camera + ".png"] = raw
        source_files[path] = sha(raw)
        instruction = row["pack_instruction"]
        public_text(instruction.encode())
        cameras.append({"camera_id": camera, "image": "images/cameras/" + camera + ".png",
                        "car_question_eligible": row["car_question_eligible"], "instruction": instruction})
    if synthetic_only:
        require(clock["run_id"].startswith("SYNTHETIC"), "SYNTHETIC_RUN_REQUIRED")
    return clock, cameras, images, raw_pins, source_files


def build_pack(output, *, inputs, synthetic_only=False):
    require(synthetic_only, "CONTRACT_UNSELECTED: coordinator must select manifest version/eligibility before production packing")
    # Keep the exact existing columns and locked-field definitions.
    import sys
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    sys.path.insert(0, str(scripts))
    from build_team_review_pack import TEXT_COLUMNS, REVIEW_COLUMNS, LOCKED
    output = Path(output).absolute()
    archive = output.with_suffix(".zip")
    require(output.resolve() == output and output.parent.is_dir() and not output.exists() and not archive.exists(), "NEW_CANONICAL_OUTPUT_REQUIRED")
    require(not output.is_relative_to(Path(__file__).resolve().parents[3]), "OUTPUT_OUTSIDE_REPO_REQUIRED")
    require(shutil.disk_usage(output.parent).free >= 8 * 1024**3, "DISK_BELOW_8_GIB")
    clock, cameras, images, pins, source_files = inputs_from_files(inputs, synthetic_only)
    start = datetime.fromisoformat(clock["wall_origin"])
    require(start.utcoffset() == timedelta(hours=8), "DECLARED_OFFSET_MISMATCH")
    end = start + timedelta(microseconds=clock["source_duration_us"])
    data = {"fixture_role": "SYNTHETIC" if synthetic_only else "AUTHORING_CANDIDATE",
            "columns": TEXT_COLUMNS, "row_ids": [f"Q{i:04d}" for i in range(1, 15)],
            "row_groups": {"Q3_MIN": [f"Q{i:04d}" for i in range(1, 9)],
                           "Q1_EXTRA": [f"Q{i:04d}" for i in range(9, 13)],
                           "OPTIONAL": [f"Q{i:04d}" for i in range(13, 15)]},
            "run_id": clock["run_id"], "clock_id": clock["clock_id"], "cameras": cameras,
            "time_window": {"start": start.isoformat(), "end_exclusive": end.isoformat(), "timezone": clock["timezone"]},
            "note_format": "q1q3-note-format.v2", "required_rows": 12,
            "dropdowns": {"classes": ["人", "車", "相機"], "targets": ["追人", "只問鏡頭"],
                          "ask": ["是", "否"], "results": ["找得到", "找不到", "不支援", "超出時間", "反問"]},
            "keywords": {"找得到": ["完整找到"], "找不到": ["完整未找到"],
                "不支援": ["類別不支援", "條件不支援", "身分不支援", "需私有真值", "跨run身分"],
                "超出時間": ["完全超時"], "反問": ["需要澄清", "單run範圍"],
                "": ["部分涵蓋", "時間無效", "解析失敗", "只測解析"]},
            "quotas": {"A": 2, "B": 2, "B_color": 1, "C": 2, "D": 1, "E": 1, "Q1": 6,
                       "found": 2, "absent": 1, "outside": 1, "partial": 1, "dated": 1, "camera": 1},
            "help_texts": {"sentence": "由你自行構思；先寫句子再判斷，最多200字。",
                           "time": "不要轉成試算表序號，也不要自行補日期。",
                           "explanation": "只說明你的判斷。不要參考其他人的題目或系統結果。"},
            "vocabulary_status": "PROVISIONAL", "candidate_colors": ["紅", "紅色", "紅衣", "藍", "藍色", "藍衣"]}
    payloads = dict(images)
    payloads["DATA.json"] = canonical(data) + b"\n"
    payloads["data.js"] = b"window.PACK_DATA=" + canonical(data) + b";\n"
    for name in ("START_HERE.html", "app.js", "style.css", "tools/verify_pack.py", "README.txt"):
        payloads[name] = (ASSETS / name).read_bytes()
    text = csv_bytes(TEXT_COLUMNS, [{TEXT_COLUMNS[0]: rid} for rid in data["row_ids"]])
    review = csv_bytes(REVIEW_COLUMNS, [])
    payloads.update({TEXT_FILE: text, "templates/情境.csv": text, REVIEW_FILE: review, "templates/審查表.csv": review,
                     "A_文字情境/範例.csv": csv_bytes(TEXT_COLUMNS, [{TEXT_COLUMNS[0]: f"示意{i}", TEXT_COLUMNS[1]: "〈由作答者自行構思的句子〉", TEXT_COLUMNS[-1]: "填法示意，不匯入評估"} for i in range(1, 4)]),
                     "RETURN/README.txt": "只放匯出的回覆CSV。未完成時保留_INCOMPLETE。請勿以試算表改存。\n".encode(),
                     "s1/README.txt": "審圖段尚待加入，本候選尚未發送。\n".encode(),
                     "s0/README.txt": "補交段尚待加入，本候選尚未發送。\n".encode(),
                     "catalog/鏡頭目錄.csv": csv_bytes(["camera_id", "中文說法", "圖檔", "出題提醒"],
                         [{"camera_id": c["camera_id"], "中文說法": "UNKNOWN（尚無正式別名）", "圖檔": c["image"], "出題提醒": c["instruction"]} for c in cameras]),
                     "catalog/時間範圍.csv": csv_bytes(["開始", "結束(不含)", "時區", "clock_mapping_sha256"],
                         [{"開始": data["time_window"]["start"], "結束(不含)": data["time_window"]["end_exclusive"], "時區": data["time_window"]["timezone"], "clock_mapping_sha256": pins["clock"]}]),
                     "catalog/詞表.csv": csv_bytes(["說法", "種類", "狀態"],
                         [{"說法": v, "種類": "類別", "狀態": "PROVISIONAL；只依附圖，不代表模型結果"} for v in ["人／人物／行人", "車／汽車／轎車", "椅子", "桌子／餐桌"]]
                         + [{"說法": v, "種類": "顏色（僅人物）", "狀態": "PROVISIONAL；候選說法，正式詞表UNKNOWN"} for v in data["candidate_colors"]])})
    for name, raw in payloads.items():
        if not name.endswith(".png"):
            public_text(raw)
    manifest = {"schema_version": "team-review-pack.v1", "version": "v1", "evaluation_eligible": False,
                "guide_sha256": "0f2ed0a92ca55b6fc68f04af03a7da286ef33a8eedc51db74847cf9078bc8cf6",
                "system_claims_sha256": sha(b"[]"), "files": {k: sha(v) for k, v in sorted(payloads.items())},
                "editable_files": {TEXT_FILE: {"template_ref": "templates/情境.csv", "locked_columns": LOCKED[TEXT_FILE]},
                                   REVIEW_FILE: {"template_ref": "templates/審查表.csv", "locked_columns": LOCKED[REVIEW_FILE]}},
                "sampling": {"method": "NO_SYSTEM_CLAIMS_AUTHORING_ONLY", "seed": "NONE", "requested": 0, "actual": 0, "positive": 0, "negative": 0, "shortfall": 0}, "samples": []}
    payloads["MANIFEST.json"] = canonical(manifest) + b"\n"
    for path, digest in source_files.items():
        require(sha(regular(path).read_bytes()) == digest, "SOURCE_CHANGED_DURING_BUILD")
    output.mkdir()
    for name, raw in sorted(payloads.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(raw)
    # UTF-8 flag for ASCII entries too; no platform-specific timestamps/attrs.
    class UTF8Info(zipfile.ZipInfo):
        def _encodeFilenameFlags(self):
            return self.filename.encode("utf-8"), self.flag_bits | 0x800
    with archive.open("xb") as handle, zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_STORED) as packed:
        for name, raw in sorted(payloads.items()):
            info = UTF8Info(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 3, 0o100644 << 16
            packed.writestr(info, raw)
    return {"phase": "S2_FRAMEWORK_ONLY", "release_authorized": False, "formal_acceptance": "NOT_EVALUATED",
            "fixture_role": data["fixture_role"], "pack_path": str(output), "zip_path": str(archive),
            "manifest_sha256": sha(payloads["MANIFEST.json"]), "zip_sha256": sha(archive.read_bytes()),
            "source_pins": pins, "files": len(payloads), "missing_sections": ["s0", "s1"]}
