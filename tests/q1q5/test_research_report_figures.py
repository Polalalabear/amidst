"""Tests for W-A9 (#427) reproducible research report tables and deterministic PNG figures."""
from __future__ import annotations

import csv
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "research"))
import generate_report_tables_and_figures as gr  # noqa: E402


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), list(reader)


def _parse_png_chunks(raw: bytes) -> list[tuple[bytes, bytes]]:
    assert raw.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG signature"
    pos = 8
    chunks: list[tuple[bytes, bytes]] = []
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        tag = raw[pos + 4 : pos + 8]
        payload = raw[pos + 8 : pos + 8 + length]
        crc_expected = struct.unpack(">I", raw[pos + 8 + length : pos + 12 + length])[0]
        crc_actual = zlib.crc32(tag + payload) & 0xFFFFFFFF
        assert crc_actual == crc_expected, f"PNG CRC mismatch in chunk {tag!r}"
        chunks.append((tag, payload))
        pos += 12 + length
    assert pos == len(raw)
    return chunks


def test_synthetic_tables_headers_row_counts_and_formatting(tmp_path: Path) -> None:
    rc = gr.main(["--synthetic", "--out", str(tmp_path)])
    assert rc == 0

    # 1. M0..M4 Comparison Table
    h1, rows1 = _read_csv_rows(tmp_path / "table_m0_m4_comparison.csv")
    assert h1 == gr.M0_M4_COLUMNS
    assert len(rows1) == 5
    assert [r["arm_id"] for r in rows1] == ["RULE_ONLY", "M1", "M2", "M3", "M4"]
    rule_row = rows1[0]
    assert rule_row["data_status"] == "SYNTHETIC"
    assert rule_row["n_events_total"] == "20"
    assert rule_row["n_events_scored"] == "18"
    assert rule_row["n_events_abstained"] == "2"
    assert rule_row["action_match_rate_pct"] == "66.67"
    assert rule_row["switch_latency_median_ms"] == "525.00"
    assert rule_row["switch_latency_p90_ms"] == "810.00"
    assert rule_row["false_handoff_rate_pct"] == "16.67"
    assert rule_row["abstention_rate_pct"] == "10.00"

    # 2. Q4 Presence Accuracy Table
    h2, rows2 = _read_csv_rows(tmp_path / "table_q4_presence_accuracy.csv")
    assert h2 == gr.Q4_COLUMNS
    assert len(rows2) == 4
    assert [r["stratum"] for r in rows2] == ["A4-1", "B4-1", "COMPLEX", "ALL"]
    all_q4 = rows2[-1]
    assert all_q4["data_status"] == "SYNTHETIC"
    assert (all_q4["n_total"], all_q4["n_decided"], all_q4["n_unknown"]) == ("92", "83", "9")
    assert (all_q4["tp"], all_q4["fp"], all_q4["tn"], all_q4["fn"]) == ("36", "8", "33", "6")
    assert all_q4["accuracy_pct"] == "83.13"
    assert all_q4["precision_pct"] == "81.82"
    assert all_q4["recall_pct"] == "85.71"
    assert all_q4["f1_pct"] == "83.72"
    assert all_q4["unknown_rate_pct"] == "9.78"

    # 3. Q5 Switch Consistency Table
    h3, rows3 = _read_csv_rows(tmp_path / "table_q5_switch_consistency.csv")
    assert h3 == gr.Q5_COLUMNS
    assert len(rows3) == 5
    assert [r["decision_category"] for r in rows3] == ["KEEP", "HANDOFF", "LOST", "ABSTAIN", "ALL"]
    all_q5 = rows3[-1]
    assert all_q5["data_status"] == "SYNTHETIC"
    assert (all_q5["n_windows_total"], all_q5["n_windows_evaluated"], all_q5["n_unknown"]) == ("63", "58", "5")
    assert (all_q5["n_agreed"], all_q5["n_disagreed"]) == ("50", "8")
    assert all_q5["agreement_rate_pct"] == "86.21"
    assert all_q5["median_window_latency_ms"] == "310.00"


def test_png_figures_valid_structure_and_byte_for_byte_deterministic(tmp_path: Path) -> None:
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"
    assert gr.main(["--synthetic", "--out", str(run1)]) == 0
    assert gr.main(["--synthetic", "--out", str(run2)]) == 0

    png_names = (
        "fig_m0_m4_comparison.png",
        "fig_q4_presence_accuracy.png",
        "fig_q5_switch_consistency.png",
    )
    for name in png_names:
        b1 = (run1 / name).read_bytes()
        b2 = (run2 / name).read_bytes()
        assert b1 == b2, f"{name} is not byte-for-byte deterministic across runs"

        chunks = _parse_png_chunks(b1)
        tags = [t for t, _ in chunks]
        assert tags[0] == b"IHDR"
        assert b"IDAT" in tags
        assert tags[-1] == b"IEND"

        width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
        assert (width, height) == (720, 420)
        assert (bit_depth, color_type, comp, filt, interlace) == (8, 2, 0, 0, 0)

        idat_bytes = b"".join(payload for tag, payload in chunks if tag == b"IDAT")
        decompressed = zlib.decompress(idat_bytes)
        assert len(decompressed) == height * (1 + width * 3)


def test_manifest_sha256_matches_generated_files_and_doc(tmp_path: Path) -> None:
    assert gr.main(["--synthetic", "--out", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_origin"] == "SYNTHETIC"
    assert manifest["real_data_status"] == "PENDING_REAL_DATA"
    assert len(manifest["files"]) == 9

    doc_text = (REPO_ROOT / "docs" / "evaluation" / "RESEARCH_REPORT_TABLES_AND_FIGURES_V1.md").read_text(encoding="utf-8")

    for entry in manifest["files"]:
        file_path = tmp_path / entry["name"]
        assert file_path.is_file()
        raw = file_path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        assert entry["sha256"] == actual_sha
        assert entry["size_bytes"] == len(raw)
        assert manifest["sha256_by_file"][entry["name"]] == actual_sha
        assert actual_sha in doc_text, f"SHA-256 for {entry['name']} missing from evaluation doc"


def test_missing_or_partial_real_data_never_fabricates_values(tmp_path: Path) -> None:
    empty_in = tmp_path / "empty_real_input"
    empty_in.mkdir()
    out_empty = tmp_path / "out_empty"

    assert gr.main(["--input-dir", str(empty_in), "--out", str(out_empty)]) == 0
    manifest = json.loads((out_empty / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_origin"] == "PENDING_REAL_DATA"
    assert manifest["real_data_status"] == "PENDING_REAL_DATA"
    assert all(v == "PENDING_REAL_DATA" for v in manifest["table_statuses"].values())

    _, rows1 = _read_csv_rows(out_empty / "table_m0_m4_comparison.csv")
    for r in rows1:
        assert r["data_status"] == "PENDING_REAL_DATA"
        assert r["action_match_rate_pct"] == "UNKNOWN"
        assert r["switch_latency_median_ms"] == "UNKNOWN"

    _, rows2 = _read_csv_rows(out_empty / "table_q4_presence_accuracy.csv")
    for r in rows2:
        assert r["data_status"] == "PENDING_REAL_DATA"
        assert r["accuracy_pct"] == "UNKNOWN"
        assert r["f1_pct"] == "UNKNOWN"

    _, rows3 = _read_csv_rows(out_empty / "table_q5_switch_consistency.csv")
    for r in rows3:
        assert r["data_status"] == "PENDING_REAL_DATA"
        assert r["agreement_rate_pct"] == "UNKNOWN"

    # Partial real data: only A4-1 provided in q4_presence.json, with 1 TP and 1 UNKNOWN review
    partial_in = tmp_path / "partial_real_input"
    partial_in.mkdir()
    (partial_in / "q4_presence.json").write_text(
        json.dumps({
            "samples": [
                {"sample_id": "s1", "stratum": "A4-1", "system_positive": True, "human_tf": "T"},
                {"sample_id": "s2", "stratum": "A4-1", "system_positive": False, "human_tf": "UNKNOWN"},
            ]
        }),
        encoding="utf-8",
    )
    out_partial = tmp_path / "out_partial"
    assert gr.main(["--input-dir", str(partial_in), "--out", str(out_partial)]) == 0
    _, q4_partial = _read_csv_rows(out_partial / "table_q4_presence_accuracy.csv")
    by_stratum = {r["stratum"]: r for r in q4_partial}
    assert by_stratum["A4-1"]["n_total"] == "2"
    assert by_stratum["A4-1"]["n_decided"] == "1"
    assert by_stratum["A4-1"]["n_unknown"] == "1"
    assert by_stratum["A4-1"]["accuracy_pct"] == "100.00"
    assert by_stratum["A4-1"]["unknown_rate_pct"] == "50.00"
    # Unmeasured B4-1 and COMPLEX strata remain UNKNOWN, never imputed
    assert by_stratum["B4-1"]["n_total"] == "UNKNOWN"
    assert by_stratum["B4-1"]["accuracy_pct"] == "UNKNOWN"
    assert by_stratum["COMPLEX"]["accuracy_pct"] == "UNKNOWN"


def test_mutually_exclusive_cli_flags(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        gr.generate_report(tmp_path, synthetic=True, input_dir=tmp_path)
    with pytest.raises(ValueError):
        gr.generate_report(tmp_path, synthetic=False, input_dir=None)
