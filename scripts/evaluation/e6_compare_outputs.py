"""Compare independently generated diagnostics to Claude's CSV outputs, never its scripts."""

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path


def compare(diagnostics, reference):
    d = json.loads(diagnostics.read_text())
    output = {
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "diagnostics_sha256": hashlib.sha256(diagnostics.read_bytes()).hexdigest(),
        "checked_cells": 0,
        "differences": [],
        "unavailable": [],
    }
    mapping = {
        "接回率": "eventually",
        "接回延遲s": "delay_s",
        "接回前認錯s": "pre_reacquire_wrong_s",
        "接回前失聯s": "pre_reacquire_lost_s",
        "接回後認錯s": "post_reacquire_wrong_s",
        "持續2s跟對率": "sustained_2s",
    }
    for row in csv.DictReader(reference.open(encoding="utf-8-sig")):
        case = d["cases"][row["case"]]
        for field, old in row.items():
            if not old or not field.startswith(("B1_", "A2_", "AO_")):
                continue
            arm, name = field.split("_", 1)
            runs = case["arms"][arm]
            values = []
            for run in runs:
                if row["event"].startswith("開頭"):
                    value = run["opening_wrong_s"] if name == "接回後認錯s" else None
                else:
                    lo = round(float(row["gt_start_s"]) * 5)
                    b = next(e for e in run["blind_events"] if e["start_tick"] == lo)
                    r = next((e for e in run["returns"] if e["blind_start_tick"] == lo), None)
                    if name == "盲區誤鎖s":
                        value = b["false_lock_s"]
                    elif name == "入盲前已認錯":
                        value = b["pre_return_wrong"]
                    elif r is None:
                        value = None
                    elif name == "接回後可見s":
                        value = (
                            (r["visible_until_tick"] - r["first_correct_tick"]) / 5
                            if r["first_correct_tick"] is not None
                            else 0
                        )
                    else:
                        value = r.get(mapping.get(name))
                if value is not None:
                    values.append(value)
            item = {
                "case": row["case"],
                "event": row["event"],
                "field": field,
                "reference": float(old),
            }
            if not values:
                output["unavailable"].append(item)
                continue
            item["independent"] = statistics.mean(values)
            digits = len(old.partition(".")[2])
            output["checked_cells"] += 1
            if abs(item["independent"] - float(old)) > 0.50001 * 10**-digits:
                output["differences"].append(item)
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diagnostics", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("OUTPUT_EXISTS")
    result = compare(a.diagnostics, a.reference)
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
