#!/usr/bin/env python3
"""Read-only verification of the supplied authoring pack and optional return."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re


def returned_rows(rows, data):
    if not rows or rows[0] != data["columns"] or len(rows) != len(data["row_ids"]) + 1:
        raise ValueError("CSV_COLUMNS_OR_ROW_COUNT")
    if [r[0] for r in rows[1:] if r] != data["row_ids"]:
        raise ValueError("LOCKED_IDS_CHANGED")
    counts = {k: 0 for k in [*data["quotas"], "A_person", "whole"]}
    incomplete, reasons = [], set()
    cameras = {c["camera_id"]: c for c in data["cameras"]}
    for i, row in enumerate(rows[1:]):
        if len(row) != 10:
            raise ValueError("CSV_COLUMNS_INVALID")
        rid, text, cls, color, start, end, camera, ask, result, note = row
        if any(v.startswith(("\t", "\r")) or v.lstrip().startswith(("=", "+", "-", "@")) for v in row):
            raise ValueError("FORMULA_REJECTED")
        if "\n" in text or "\r" in text or len(text) > 200:
            raise ValueError("SENTENCE_LINE_OR_LENGTH")
        if all(v == "" for v in row[1:]):
            if rid not in data["row_groups"]["OPTIONAL"]:
                incomplete.append(rid + ":REQUIRED_ROW_EMPTY")
            continue
        if cls not in data["dropdowns"]["classes"] or ask not in {"是", "否"} or result not in data["keywords"]:
            raise ValueError("CLOSED_VALUE_INVALID")
        if result == "反問" and ask != "是":
            raise ValueError("CLARIFICATION_CONTRADICTION")
        if "｜說明=" not in note:
            raise ValueError("NOTE_FORMAT_INVALID")
        head, explanation = note.split("｜說明=", 1)
        parts = head.split("｜")
        if len(parts) not in {2, 3} or not parts[0].startswith("關鍵字=") or not parts[1].startswith("目標="):
            raise ValueError("NOTE_FORMAT_INVALID")
        reason, target = parts[0][4:], parts[1][3:]
        allowed = set(data["keywords"][result])
        if reason not in allowed or (target not in data["dropdowns"]["targets"] if cls == "人" else target != "不適用"):
            raise ValueError("NOTE_TARGET_OR_REASON_INVALID")
        if rid in data["row_groups"]["Q1_EXTRA"] and cls != "相機":
            raise ValueError("EXTRA_ROW_CLASS_INVALID")
        evidence = {}
        if len(parts) == 3:
            if not parts[2].startswith("鏡頭="):
                raise ValueError("NOTE_FORMAT_INVALID")
            for item in parts[2][3:].split(","):
                pair = item.split(":")
                if len(pair) != 2 or pair[0] not in cameras or pair[0] in evidence or pair[1] not in {"看得到", "看不到", "看不清"}:
                    raise ValueError("EVIDENCE_FORMAT_INVALID")
                evidence[pair[0]] = pair[1]
        selected = {c for c in cameras if c in camera} or set(cameras)
        if cls == "車" and (not any(c in camera for c in cameras) or any(not cameras[c]["car_question_eligible"] for c in selected)):
            raise ValueError("CAR_CAMERA_UNSELECTED")
        needs_evidence = cls in {"相機", "車"} and result in {"找得到", "找不到"}
        pending = (not text.strip() or (needs_evidence and set(evidence) != selected)
                   or "看不清" in evidence.values() or explanation.startswith("UNKNOWN："))
        needs_explanation = (not start.strip() or not end.strip() or result in {"", "反問", "不支援"}
                             or pending or (ask == "是" and result != "反問"))
        if needs_explanation and not explanation.strip():
            pending = True
        if pending:
            incomplete.append(rid + ":ROW_PENDING")
            continue
        if rid in data["row_groups"]["OPTIONAL"]:
            continue
        explicit = bool(start.strip() and end.strip())
        parsed = reason in {"完整找到", "完整未找到", "完全超時", "部分涵蓋", "只測解析"}
        if parsed and not explicit:
            counts["whole"] += 1
        if rid in data["row_groups"]["Q3_MIN"]:
            if parsed and explicit and cls in {"相機", "車"}:
                counts["A"] += 1
            if parsed and explicit and cls == "人":
                if target == "追人":
                    counts["B"] += 1
                    counts["B_color"] += bool(color.strip())
                else:
                    counts["A_person"] += 1
            if result == "反問":
                counts["C"] += 1
                reasons.add(reason + ":" + explanation)
            if reason == "類別不支援":
                counts["D"] += 1
            if reason == "條件不支援":
                counts["E"] += 1
        if explicit and cls in {"相機", "車"} and reason in {"完整找到", "完整未找到", "完全超時", "部分涵蓋"}:
            counts["Q1"] += 1
            key = {"完整找到": "found", "完整未找到": "absent", "完全超時": "outside", "部分涵蓋": "partial"}[reason]
            counts[key] += 1
        if re.search(r"\d{4}-\d{2}-\d{2}", text) and re.search(r"[+-]\d{2}:\d{2}|Asia/Taipei|台北|臺北|UTC", text):
            counts["dated"] += 1
        if any(c in text for c in cameras):
            counts["camera"] += 1
    incomplete += ["QUOTA:" + k for k, n in data["quotas"].items() if counts[k] < n]
    if len(reasons) < 2:
        incomplete.append("CLARIFICATION_REASONS_NOT_DISTINCT")
    return {"quota_counts": counts, "incomplete_required": bool(incomplete), "incomplete_reasons": incomplete}


def check(root, expected, returned=None):
    root = root.absolute()
    if root.resolve() != root:
        raise ValueError("SYMLINK_REJECTED")
    manifest_path = root / "MANIFEST.json"
    if manifest_path.is_symlink():
        raise ValueError("SYMLINK_REJECTED")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("MANIFEST_PIN_MISMATCH")
    manifest = json.loads(raw)
    if manifest.get("schema_version") != "team-review-pack.v1":
        raise ValueError("UNKNOWN_VERSION")
    files, missing = manifest["files"], []
    editable = manifest["editable_files"]
    for name, pin in files.items():
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.resolve() != path:
            raise ValueError("UNSAFE_PATH")
        if not path.exists():
            if name in {"templates/情境.csv", "templates/審查表.csv"}:
                missing.append(name)
                continue
            raise ValueError("MISSING_FILE:" + name)
        if not path.is_file():
            raise ValueError("REGULAR_FILE_REQUIRED")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("FILE_PIN_MISMATCH:" + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    extras = actual - set(files) - {"MANIFEST.json"}
    if any(not name.startswith("RETURN/") for name in extras):
        raise ValueError("UNLISTED_FILE")
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("SYMLINK_REJECTED")
    result = {}
    if returned is not None:
        returned = returned.absolute()
        if returned.resolve() != returned or not returned.is_file():
            raise ValueError("REGULAR_RETURN_REQUIRED")
        data = json.loads((root / "DATA.json").read_bytes())
        reader = csv.reader(io.StringIO(returned.read_bytes().decode("utf-8-sig"), newline=""))
        result = returned_rows(list(reader), data)
    return {**result, "status": "VALID_WITH_WARNINGS" if missing else "VERIFIED", "missing_templates": sorted(missing),
            "warnings": ["TEMPLATE_MISSING:" + name for name in sorted(missing)],
            "reason_codes": ["TEMPLATE_MISSING"] if missing else [], "answers_verified": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--returned-csv", type=Path)
    a = p.parse_args()
    try:
        result = check(Path(__file__).resolve().parents[1], a.manifest_sha256, a.returned_csv)
        code = 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, csv.Error) as exc:
        result, code = {"status": "INVALID", "reason": str(exc)}, 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
