#!/usr/bin/env python3
"""Reproducible research report tables (CSV + Markdown) and deterministic PNG figures (Issue #427 / W-A9).

Generates report artifacts for:
1. Baseline (RULE_ONLY) vs M1..M4 model combinations across event metrics:
   - table_m0_m4_comparison.csv, table_m0_m4_comparison.md, fig_m0_m4_comparison.png
2. Q4 T/F presence accuracy, precision, recall, F1, and UNKNOWN rate:
   - table_q4_presence_accuracy.csv, table_q4_presence_accuracy.md, fig_q4_presence_accuracy.png
3. Q5 camera switch decision-window consistency (KEEP / HANDOFF / LOST / ABSTAIN agreement):
   - table_q5_switch_consistency.csv, table_q5_switch_consistency.md, fig_q5_switch_consistency.png
4. Output manifest with SHA-256 hashes and provenance:
   - manifest.json

Rules:
- Never reads Ground Truth, raw recordings, or RGB frames.
- Never imputes or fabricates missing values: missing/unmeasured values remain UNKNOWN or PENDING_REAL_DATA
  and are excluded from numerators and denominators.
- PNG figures are rendered with a pure-Python stdlib (zlib + struct) rasterizer so outputs are 100%
  byte-for-byte deterministic across platforms without GUI or font-engine variance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
import zlib
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"
PENDING_REAL_DATA = "PENDING_REAL_DATA"
SYNTHETIC = "SYNTHETIC"
REAL_DATA = "REAL_DATA"
MISSING_TOKENS = {"", "UNKNOWN", "MISSING", "NOT_RUN", "PENDING_REAL_DATA"}

M0_M4_ARMS: tuple[tuple[str, str], ...] = (
    ("RULE_ONLY", "Baseline rule-only controller (M0)"),
    ("M1", "Sequential agent with rule fallback (M1)"),
    ("M2", "Scorer v2 guarded complex-scene evaluation (M2)"),
    ("M3", "LLM Q3 query parser with rule fallback (M3)"),
    ("M4", "Candidate LLM model sweep best-balanced arm (M4)"),
)

Q4_STRATA: tuple[str, ...] = ("A4-1", "B4-1", "COMPLEX", "ALL")
Q5_CATEGORIES: tuple[str, ...] = ("KEEP", "HANDOFF", "LOST", "ABSTAIN", "ALL")

M0_M4_COLUMNS: list[str] = [
    "arm_id",
    "model_combination",
    "data_status",
    "n_events_total",
    "n_events_scored",
    "n_events_abstained",
    "action_match_rate_pct",
    "switch_latency_median_ms",
    "switch_latency_p90_ms",
    "false_handoff_rate_pct",
    "abstention_rate_pct",
]

Q4_COLUMNS: list[str] = [
    "stratum",
    "data_status",
    "n_total",
    "n_decided",
    "tp",
    "fp",
    "tn",
    "fn",
    "n_unknown",
    "accuracy_pct",
    "precision_pct",
    "recall_pct",
    "f1_pct",
    "unknown_rate_pct",
]

Q5_COLUMNS: list[str] = [
    "decision_category",
    "data_status",
    "n_windows_total",
    "n_windows_evaluated",
    "n_agreed",
    "n_disagreed",
    "n_unknown",
    "agreement_rate_pct",
    "median_window_latency_ms",
]


def is_unknown(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().upper() in MISSING_TOKENS)


def as_float(value: Any) -> float | None:
    if is_unknown(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def percentile_nearest_rank(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, math.ceil(p * len(ordered)) - 1)
    return ordered[idx]


def fmt_num(value: Any, digits: int = 2) -> str:
    if value is None or is_unknown(value):
        return UNKNOWN
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Synthetic dataset (used only with --synthetic)
# ---------------------------------------------------------------------------

def build_synthetic_dataset() -> dict[str, Any]:
    """Deterministic synthetic dataset covering M0..M4, Q4 T/F presence, and Q5 switch windows."""
    m0_m4_events: list[dict[str, Any]] = []

    arm_specs = [
        # (arm_id, n_total, n_abstain, matched_latencies_ms, mismatched_count, false_handoff_count, handoff_opps)
        ("RULE_ONLY", 20, 2, [380.0, 400.0, 420.0, 450.0, 480.0, 510.0, 540.0, 600.0, 640.0, 720.0, 810.0, 1200.0], 6, 3, 18),
        ("M1", 20, 3, [410.0, 440.0, 470.0, 500.0, 520.0, 550.0, 590.0, 620.0, 660.0, 700.0, 760.0, 820.0, 910.0, 980.0], 3, 2, 17),
        ("M2", 20, 4, [390.0, 415.0, 445.0, 470.0, 495.0, 520.0, 545.0, 575.0, 610.0, 650.0, 690.0, 740.0, 790.0, 850.0], 2, 1, 16),
        ("M3", 20, 2, [400.0, 430.0, 460.0, 490.0, 515.0, 540.0, 570.0, 600.0, 635.0, 680.0, 730.0, 780.0, 840.0, 900.0, 960.0], 3, 2, 18),
        ("M4", 20, 2, [360.0, 385.0, 410.0, 435.0, 460.0, 485.0, 510.0, 535.0, 560.0, 590.0, 625.0, 660.0, 700.0, 745.0, 790.0, 830.0], 2, 1, 18),
    ]

    for arm_id, n_total, n_abstain, matched_lats, n_mismatch, n_fh, n_hopps in arm_specs:
        idx = 0
        for lat in matched_lats:
            idx += 1
            m0_m4_events.append({
                "arm_id": arm_id,
                "event_id": f"SYN-{arm_id}-e{idx:02d}",
                "scored": True,
                "abstained": False,
                "match": True,
                "latency_ms": lat,
                "handoff_opportunity": idx <= n_hopps,
                "false_handoff": False,
            })
        for m_i in range(n_mismatch):
            idx += 1
            m0_m4_events.append({
                "arm_id": arm_id,
                "event_id": f"SYN-{arm_id}-e{idx:02d}",
                "scored": True,
                "abstained": False,
                "match": False,
                "latency_ms": None,
                "handoff_opportunity": idx <= n_hopps,
                "false_handoff": m_i < n_fh,
            })
        for _ in range(n_abstain):
            idx += 1
            m0_m4_events.append({
                "arm_id": arm_id,
                "event_id": f"SYN-{arm_id}-e{idx:02d}",
                "scored": False,
                "abstained": True,
                "match": UNKNOWN,
                "latency_ms": None,
                "handoff_opportunity": False,
                "false_handoff": False,
            })
        assert idx == n_total

    # Q4 synthetic T/F review samples per stratum
    # Format: (stratum, tp_count, fp_count, tn_count, fn_count, unknown_count)
    q4_specs = [
        ("A4-1", 14, 2, 13, 1, 2),
        ("B4-1", 12, 3, 11, 2, 2),
        ("COMPLEX", 10, 3, 9, 3, 5),
    ]
    q4_samples: list[dict[str, Any]] = []
    for stratum, tp_c, fp_c, tn_c, fn_c, unk_c in q4_specs:
        s_idx = 0
        for _ in range(tp_c):
            s_idx += 1
            q4_samples.append({"sample_id": f"SYN-Q4-{stratum}-{s_idx:02d}", "stratum": stratum, "system_positive": True, "human_tf": "T"})
        for _ in range(fp_c):
            s_idx += 1
            q4_samples.append({"sample_id": f"SYN-Q4-{stratum}-{s_idx:02d}", "stratum": stratum, "system_positive": True, "human_tf": "F"})
        for _ in range(tn_c):
            s_idx += 1
            q4_samples.append({"sample_id": f"SYN-Q4-{stratum}-{s_idx:02d}", "stratum": stratum, "system_positive": False, "human_tf": "T"})
        for _ in range(fn_c):
            s_idx += 1
            q4_samples.append({"sample_id": f"SYN-Q4-{stratum}-{s_idx:02d}", "stratum": stratum, "system_positive": False, "human_tf": "F"})
        for _ in range(unk_c):
            s_idx += 1
            q4_samples.append({"sample_id": f"SYN-Q4-{stratum}-{s_idx:02d}", "stratum": stratum, "system_positive": True, "human_tf": UNKNOWN})

    # Q5 synthetic decision windows per expected category
    # Format: (category, agreed_latencies_ms, disagreed_count, unknown_count)
    q5_specs = [
        ("KEEP", [120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0, 200.0, 210.0, 220.0, 230.0, 240.0, 250.0, 260.0, 270.0, 280.0, 300.0], 2, 1),
        ("HANDOFF", [420.0, 450.0, 480.0, 510.0, 540.0, 570.0, 600.0, 630.0, 660.0, 690.0, 720.0, 750.0, 780.0, 840.0], 3, 1),
        ("LOST", [310.0, 340.0, 370.0, 400.0, 430.0, 460.0, 490.0, 520.0, 550.0, 580.0], 2, 2),
        ("ABSTAIN", [190.0, 210.0, 230.0, 250.0, 270.0, 290.0, 310.0, 330.0], 1, 1),
    ]
    q5_windows: list[dict[str, Any]] = []
    for cat, lats, n_dis, n_unk in q5_specs:
        w_idx = 0
        for lat in lats:
            w_idx += 1
            q5_windows.append({
                "window_id": f"SYN-Q5-{cat}-{w_idx:02d}",
                "expected_category": cat,
                "observed_category": cat,
                "latency_ms": lat,
            })
        alt = "KEEP" if cat != "KEEP" else "HANDOFF"
        for _ in range(n_dis):
            w_idx += 1
            q5_windows.append({
                "window_id": f"SYN-Q5-{cat}-{w_idx:02d}",
                "expected_category": cat,
                "observed_category": alt,
                "latency_ms": 950.0,
            })
        for _ in range(n_unk):
            w_idx += 1
            q5_windows.append({
                "window_id": f"SYN-Q5-{cat}-{w_idx:02d}",
                "expected_category": cat,
                "observed_category": UNKNOWN,
                "latency_ms": None,
            })

    return {
        "data_origin": SYNTHETIC,
        "m0_m4_events": m0_m4_events,
        "q4_samples": q4_samples,
        "q5_windows": q5_windows,
    }


# ---------------------------------------------------------------------------
# Metric computations (never fabricate or impute missing values)
# ---------------------------------------------------------------------------

def compute_m0_m4_table(events: list[dict[str, Any]] | None, data_status_default: str) -> tuple[list[dict[str, str]], str]:
    rows: list[dict[str, str]] = []
    any_pending = False
    events_by_arm: dict[str, list[dict[str, Any]]] = {}
    if events:
        for ev in events:
            arm = str(ev.get("arm_id") or "")
            if arm:
                events_by_arm.setdefault(arm, []).append(ev)

    for arm_id, desc in M0_M4_ARMS:
        arm_events = events_by_arm.get(arm_id, [])
        if not arm_events:
            any_pending = True
            rows.append({
                "arm_id": arm_id,
                "model_combination": desc,
                "data_status": PENDING_REAL_DATA if data_status_default != SYNTHETIC else UNKNOWN,
                "n_events_total": UNKNOWN,
                "n_events_scored": UNKNOWN,
                "n_events_abstained": UNKNOWN,
                "action_match_rate_pct": UNKNOWN,
                "switch_latency_median_ms": UNKNOWN,
                "switch_latency_p90_ms": UNKNOWN,
                "false_handoff_rate_pct": UNKNOWN,
                "abstention_rate_pct": UNKNOWN,
            })
            continue

        n_total = len(arm_events)
        # Validate required fields on each event:
        # Each event must have an event_id, boolean abstained, and boolean scored.
        # If fields are missing/unmeasured, missing is NEVER treated as false or 0.
        has_valid_event_ids = all(
            isinstance(e.get("event_id"), (str, int)) and str(e.get("event_id")).strip()
            for e in arm_events
        )
        known_abstained_events = [e for e in arm_events if isinstance(e.get("abstained"), bool)]
        known_scored_events = [e for e in arm_events if isinstance(e.get("scored"), bool)]

        if not has_valid_event_ids or len(known_abstained_events) != n_total or len(known_scored_events) != n_total:
            # Events in this arm are missing required fields or unmeasured
            any_pending = True
            rows.append({
                "arm_id": arm_id,
                "model_combination": desc,
                "data_status": PENDING_REAL_DATA if data_status_default != SYNTHETIC else UNKNOWN,
                "n_events_total": UNKNOWN,
                "n_events_scored": UNKNOWN,
                "n_events_abstained": UNKNOWN,
                "action_match_rate_pct": UNKNOWN,
                "switch_latency_median_ms": UNKNOWN,
                "switch_latency_p90_ms": UNKNOWN,
                "false_handoff_rate_pct": UNKNOWN,
                "abstention_rate_pct": UNKNOWN,
            })
            continue

        abstained = [e for e in arm_events if e["abstained"] is True]
        n_abstained = len(abstained)
        scored = [e for e in arm_events if e["scored"] is True and e["abstained"] is False]
        n_scored = len(scored)

        # Scored events must have boolean match
        known_matches = [e for e in scored if isinstance(e.get("match"), bool)]
        if len(known_matches) != n_scored:
            match_rate = None
        elif n_scored > 0:
            matched = [e for e in scored if e["match"] is True]
            match_rate = 100.0 * len(matched) / n_scored
        else:
            match_rate = None

        matched = [e for e in scored if e.get("match") is True]
        lats = [lat for e in matched if (lat := as_float(e.get("latency_ms"))) is not None]

        handoff_opps = [e for e in arm_events if as_bool(e.get("handoff_opportunity")) is True]
        known_fh = [e for e in handoff_opps if isinstance(e.get("false_handoff"), bool)]
        if handoff_opps and len(known_fh) == len(handoff_opps):
            false_handoffs = [e for e in handoff_opps if e["false_handoff"] is True]
            fh_rate = 100.0 * len(false_handoffs) / len(handoff_opps)
        else:
            fh_rate = None

        med_lat = statistics.median(lats) if lats else None
        p90_lat = percentile_nearest_rank(lats, 0.90) if lats else None
        abstain_rate = (100.0 * n_abstained / n_total) if n_total > 0 else None

        rows.append({
            "arm_id": arm_id,
            "model_combination": desc,
            "data_status": data_status_default,
            "n_events_total": fmt_num(n_total),
            "n_events_scored": fmt_num(n_scored),
            "n_events_abstained": fmt_num(n_abstained),
            "action_match_rate_pct": fmt_num(match_rate),
            "switch_latency_median_ms": fmt_num(med_lat),
            "switch_latency_p90_ms": fmt_num(p90_lat),
            "false_handoff_rate_pct": fmt_num(fh_rate),
            "abstention_rate_pct": fmt_num(abstain_rate),
        })

    table_status = PENDING_REAL_DATA if any_pending else data_status_default
    return rows, table_status


def _compute_q4_stratum_row(stratum: str, samples: list[dict[str, Any]], status: str) -> dict[str, str]:
    if not samples:
        return {
            "stratum": stratum,
            "data_status": PENDING_REAL_DATA if status != SYNTHETIC else UNKNOWN,
            "n_total": UNKNOWN,
            "n_decided": UNKNOWN,
            "tp": UNKNOWN,
            "fp": UNKNOWN,
            "tn": UNKNOWN,
            "fn": UNKNOWN,
            "n_unknown": UNKNOWN,
            "accuracy_pct": UNKNOWN,
            "precision_pct": UNKNOWN,
            "recall_pct": UNKNOWN,
            "f1_pct": UNKNOWN,
            "unknown_rate_pct": UNKNOWN,
        }

    tp = fp = tn = fn = n_unk = 0
    for s in samples:
        pos = as_bool(s.get("system_positive"))
        tf = str(s.get("human_tf") or "").strip().upper()
        if pos is None or tf not in ("T", "F"):
            n_unk += 1
        elif pos is True and tf == "T":
            tp += 1
        elif pos is True and tf == "F":
            fp += 1
        elif pos is False and tf == "T":
            tn += 1
        else:
            fn += 1

    n_total = len(samples)
    n_decided = tp + fp + tn + fn
    acc = (100.0 * (tp + tn) / n_decided) if n_decided > 0 else None
    prec = (100.0 * tp / (tp + fp)) if (tp + fp) > 0 else None
    rec = (100.0 * tp / (tp + fn)) if (tp + fn) > 0 else None

    # F1 calculation:
    # F1 = 2 * TP / (2 * TP + FP + FN)
    # When denominator > 0, F1 is well-defined. If TP == 0 but FP > 0 or FN > 0, F1 = 0.0%.
    # When denominator == 0 (no positive predictions and no actual positives), F1 is undefined (None -> UNKNOWN).
    f1_denom = 2 * tp + fp + fn
    f1 = (100.0 * (2 * tp) / f1_denom) if f1_denom > 0 else None
    unk_rate = (100.0 * n_unk / n_total) if n_total > 0 else None

    row_status = status
    if status != SYNTHETIC and n_decided == 0:
        row_status = PENDING_REAL_DATA

    return {
        "stratum": stratum,
        "data_status": row_status,
        "n_total": fmt_num(n_total),
        "n_decided": fmt_num(n_decided),
        "tp": fmt_num(tp),
        "fp": fmt_num(fp),
        "tn": fmt_num(tn),
        "fn": fmt_num(fn),
        "n_unknown": fmt_num(n_unk),
        "accuracy_pct": fmt_num(acc),
        "precision_pct": fmt_num(prec),
        "recall_pct": fmt_num(rec),
        "f1_pct": fmt_num(f1),
        "unknown_rate_pct": fmt_num(unk_rate),
    }


def compute_q4_table(samples: list[dict[str, Any]] | None, data_status_default: str) -> tuple[list[dict[str, str]], str]:
    rows: list[dict[str, str]] = []
    any_pending = False
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    if samples:
        for s in samples:
            st = str(s.get("stratum") or "")
            if st:
                by_stratum.setdefault(st, []).append(s)

    for stratum in Q4_STRATA:
        if stratum == "ALL":
            sub = list(samples) if samples else []
        else:
            sub = by_stratum.get(stratum, [])
        if not sub:
            any_pending = True
        row = _compute_q4_stratum_row(stratum, sub, data_status_default)
        if row.get("data_status") == PENDING_REAL_DATA:
            any_pending = True
        rows.append(row)

    table_status = PENDING_REAL_DATA if any_pending else data_status_default
    return rows, table_status


def _compute_q5_category_row(category: str, windows: list[dict[str, Any]], status: str) -> dict[str, str]:
    if not windows:
        return {
            "decision_category": category,
            "data_status": PENDING_REAL_DATA if status != SYNTHETIC else UNKNOWN,
            "n_windows_total": UNKNOWN,
            "n_windows_evaluated": UNKNOWN,
            "n_agreed": UNKNOWN,
            "n_disagreed": UNKNOWN,
            "n_unknown": UNKNOWN,
            "agreement_rate_pct": UNKNOWN,
            "median_window_latency_ms": UNKNOWN,
        }

    valid_cats = {"KEEP", "HANDOFF", "LOST", "ABSTAIN"}
    n_agreed = n_disagreed = n_unk = 0
    agreed_lats: list[float] = []
    for w in windows:
        exp = str(w.get("expected_category") or "").strip().upper()
        obs = str(w.get("observed_category") or "").strip().upper()
        if exp not in valid_cats or obs not in valid_cats:
            n_unk += 1
            continue
        if obs == exp:
            n_agreed += 1
            lat = as_float(w.get("latency_ms"))
            if lat is not None:
                agreed_lats.append(lat)
        else:
            n_disagreed += 1

    n_total = len(windows)
    n_eval = n_agreed + n_disagreed
    agree_rate = (100.0 * n_agreed / n_eval) if n_eval > 0 else None
    med_lat = statistics.median(agreed_lats) if agreed_lats else None

    row_status = status
    if status != SYNTHETIC and n_eval == 0:
        row_status = PENDING_REAL_DATA

    return {
        "decision_category": category,
        "data_status": row_status,
        "n_windows_total": fmt_num(n_total),
        "n_windows_evaluated": fmt_num(n_eval),
        "n_agreed": fmt_num(n_agreed),
        "n_disagreed": fmt_num(n_disagreed),
        "n_unknown": fmt_num(n_unk),
        "agreement_rate_pct": fmt_num(agree_rate),
        "median_window_latency_ms": fmt_num(med_lat),
    }


def compute_q5_table(windows: list[dict[str, Any]] | None, data_status_default: str) -> tuple[list[dict[str, str]], str]:
    rows: list[dict[str, str]] = []
    any_pending = False
    by_cat: dict[str, list[dict[str, Any]]] = {}
    if windows:
        for w in windows:
            cat = str(w.get("expected_category") or "").strip().upper()
            if cat:
                by_cat.setdefault(cat, []).append(w)

    for cat in Q5_CATEGORIES:
        if cat == "ALL":
            sub = list(windows) if windows else []
        else:
            sub = by_cat.get(cat, [])
        if not sub:
            any_pending = True
        row = _compute_q5_category_row(cat, sub, data_status_default)
        if row.get("data_status") == PENDING_REAL_DATA:
            any_pending = True
        rows.append(row)

    table_status = PENDING_REAL_DATA if any_pending else data_status_default
    return rows, table_status


# ---------------------------------------------------------------------------
# Pure-Python deterministic PNG renderer (stdlib struct + zlib only)
# ---------------------------------------------------------------------------

FONT_5X7: dict[str, tuple[int, ...]] = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    "_": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    "/": (0x01, 0x02, 0x04, 0x04, 0x08, 0x10, 0x00),
    "%": (0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
}


class DeterministicCanvas:
    """Pure-Python RGB raster canvas that exports deterministic PNG bytes."""

    def __init__(self, width: int, height: int, bg: tuple[int, int, int] = (252, 252, 251)) -> None:
        self.width = width
        self.height = height
        self.buf = bytearray(bg * (width * height))

    def set_px(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.buf[idx] = color[0]
            self.buf[idx + 1] = color[1]
            self.buf[idx + 2] = color[2]

    def fill_rect(self, x0: int, y0: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        x1 = min(self.width, max(0, x0 + w))
        y1 = min(self.height, max(0, y0 + h))
        x0 = max(0, x0)
        y0 = max(0, y0)
        if x1 <= x0 or y1 <= y0:
            return
        row_bytes = bytes(color) * (x1 - x0)
        span = (x1 - x0) * 3
        for y in range(y0, y1):
            start = (y * self.width + x0) * 3
            self.buf[start : start + span] = row_bytes

    def stroke_rect(self, x0: int, y0: int, w: int, h: int, color: tuple[int, int, int], hatch: bool = False) -> None:
        self.fill_rect(x0, y0, w, 1, color)
        self.fill_rect(x0, y0 + h - 1, w, 1, color)
        self.fill_rect(x0, y0, 1, h, color)
        self.fill_rect(x0 + w - 1, y0, 1, h, color)
        if hatch:
            for dy in range(1, h - 1):
                for dx in range(1, w - 1):
                    if (dx + dy) % 6 == 0:
                        self.set_px(x0 + dx, y0 + dy, color)

    def draw_text(self, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 1) -> None:
        cursor_x = x
        for ch in text.upper():
            glyph = FONT_5X7.get(ch, FONT_5X7[" "])
            for row_i, bits in enumerate(glyph):
                for col_i in range(5):
                    if (bits >> (4 - col_i)) & 1:
                        self.fill_rect(
                            cursor_x + col_i * scale,
                            y + row_i * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor_x += 6 * scale

    def to_png_bytes(self) -> bytes:
        raw_rows = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw_rows.append(0)  # filter type 0 (None)
            start = y * stride
            raw_rows.extend(self.buf[start : start + stride])

        def chunk(tag: bytes, payload: bytes) -> bytes:
            crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        idat = zlib.compress(bytes(raw_rows), level=9)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


PALETTE: tuple[tuple[int, int, int], ...] = (
    (42, 120, 214),   # blue
    (235, 104, 52),   # orange
    (44, 160, 44),    # green
    (148, 103, 189),  # purple
)


def render_grouped_bar_chart_png(
    title: str,
    subtitle: str,
    banner: str,
    categories: list[str],
    series: list[tuple[str, list[float | None]]],
    width: int = 720,
    height: int = 420,
) -> bytes:
    """Render a deterministic grouped percentage bar chart (0..100%) to PNG bytes."""
    canvas = DeterministicCanvas(width, height)
    ink = (15, 15, 15)
    muted = (120, 118, 112)
    grid = (225, 224, 217)

    canvas.draw_text(20, 16, title, ink, scale=2)
    canvas.draw_text(20, 38, subtitle, muted, scale=1)

    # Legend on top right
    leg_x = 20
    leg_y = 54
    for s_idx, (s_name, _) in enumerate(series):
        col = PALETTE[s_idx % len(PALETTE)]
        canvas.fill_rect(leg_x, leg_y, 10, 8, col)
        canvas.draw_text(leg_x + 14, leg_y + 1, s_name, ink, scale=1)
        leg_x += 14 + len(s_name) * 6 + 16

    plot_x0, plot_y0 = 64, 78
    plot_w, plot_h = width - 92, height - 138
    plot_y1 = plot_y0 + plot_h

    # Grid lines at 0%, 25%, 50%, 75%, 100%
    for pct in (0, 25, 50, 75, 100):
        gy = plot_y1 - int(round((pct / 100.0) * plot_h))
        canvas.fill_rect(plot_x0, gy, plot_w, 1, grid if pct > 0 else ink)
        label = f"{pct:3d}%"
        canvas.draw_text(plot_x0 - 30, gy - 3, label, muted, scale=1)

    # Y axis line
    canvas.fill_rect(plot_x0, plot_y0, 1, plot_h, ink)

    n_cats = max(1, len(categories))
    n_series = max(1, len(series))
    group_step = plot_w // n_cats
    bar_w = max(8, min(28, (group_step - 20) // n_series))

    for c_idx, cat_label in enumerate(categories):
        group_center = plot_x0 + c_idx * group_step + group_step // 2
        total_bars_w = n_series * bar_w + (n_series - 1) * 4
        start_x = group_center - total_bars_w // 2

        for s_idx, (_, values) in enumerate(series):
            val = values[c_idx] if c_idx < len(values) else None
            bx = start_x + s_idx * (bar_w + 4)
            color = PALETTE[s_idx % len(PALETTE)]
            if val is None:
                # Hatched placeholder bar for UNKNOWN / PENDING_REAL_DATA
                canvas.stroke_rect(bx, plot_y0 + 20, bar_w, plot_h - 20, muted, hatch=True)
                canvas.draw_text(bx + max(0, (bar_w - 18) // 2), plot_y0 + plot_h // 2, "UNK", muted, scale=1)
            else:
                clamped = max(0.0, min(100.0, val))
                bh = max(1, int(round((clamped / 100.0) * plot_h)))
                by = plot_y1 - bh
                canvas.fill_rect(bx, by, bar_w, bh, color)
                val_txt = f"{clamped:.0f}"
                canvas.draw_text(bx + max(0, (bar_w - len(val_txt) * 6) // 2), max(plot_y0, by - 10), val_txt, ink, scale=1)

        cat_x = group_center - (len(cat_label) * 6) // 2
        canvas.draw_text(cat_x, plot_y1 + 10, cat_label, ink, scale=1)

    canvas.draw_text(20, height - 18, banner, muted, scale=1)
    return canvas.to_png_bytes()


# ---------------------------------------------------------------------------
# File writers (CSV + Markdown + PNG + manifest.json)
# ---------------------------------------------------------------------------

def write_csv_and_md(
    outdir: Path,
    stem: str,
    columns: list[str],
    rows: list[dict[str, str]],
    title: str,
    banner: str,
    notes: list[str],
) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"{stem}.csv"
    md_path = outdir / f"{stem}.md"

    with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(col, UNKNOWN) for col in columns])

    lines = [
        f"# {title}",
        "",
        f"Provenance: `{banner}`",
        "",
    ]
    for note in notes:
        lines.append(f"- {note}")
    if notes:
        lines.append("")
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, UNKNOWN)) for col in columns) + " |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return csv_path, md_path


def _parse_pct(cell_val: str) -> float | None:
    if is_unknown(cell_val):
        return None
    try:
        return float(cell_val)
    except ValueError:
        return None


def inspect_and_load_input_file(
    input_dir: Path,
    filename: str,
    list_key: str,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    p = input_dir / filename
    if not p.is_file():
        return None, {
            "name": filename,
            "present": False,
            "sha256": None,
            "data_origin": PENDING_REAL_DATA,
            "evaluation_eligible": False,
            "status": PENDING_REAL_DATA,
            "record_count": 0,
            "reason": "FILE_MISSING",
        }

    raw = p.read_bytes()
    digest = sha256_bytes(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return None, {
            "name": filename,
            "present": True,
            "sha256": digest,
            "data_origin": PENDING_REAL_DATA,
            "evaluation_eligible": False,
            "status": PENDING_REAL_DATA,
            "record_count": 0,
            "reason": f"JSON_DECODE_ERROR: {exc}",
        }

    if not isinstance(payload, dict):
        return None, {
            "name": filename,
            "present": True,
            "sha256": digest,
            "data_origin": PENDING_REAL_DATA,
            "evaluation_eligible": False,
            "status": PENDING_REAL_DATA,
            "record_count": 0,
            "reason": "PAYLOAD_NOT_DICT",
        }

    records = payload.get(list_key)
    if not isinstance(records, list):
        return None, {
            "name": filename,
            "present": True,
            "sha256": digest,
            "data_origin": PENDING_REAL_DATA,
            "evaluation_eligible": False,
            "status": PENDING_REAL_DATA,
            "record_count": 0,
            "reason": f"KEY_{list_key.upper()}_NOT_LIST",
        }

    origin_raw = str(payload.get("data_origin") or "").strip().upper()
    is_synth = (origin_raw == SYNTHETIC) or (payload.get("synthetic") is True)
    eval_eligible = payload.get("evaluation_eligible")
    is_pilot = (payload.get("pilot") is True) or ("pilot" in str(payload.get("version") or "").lower())

    if is_synth:
        file_origin = SYNTHETIC
        file_status = SYNTHETIC
        eligible = False
    elif (eval_eligible is False) or is_pilot or (origin_raw == PENDING_REAL_DATA):
        file_origin = PENDING_REAL_DATA
        file_status = PENDING_REAL_DATA
        eligible = False
    elif (origin_raw == REAL_DATA) and (eval_eligible is True) and (not is_pilot):
        file_origin = REAL_DATA
        file_status = REAL_DATA
        eligible = True
    else:
        # Fail closed: unconfirmed real data contract stays PENDING_REAL_DATA
        file_origin = PENDING_REAL_DATA
        file_status = PENDING_REAL_DATA
        eligible = False

    info = {
        "name": filename,
        "present": True,
        "sha256": digest,
        "size_bytes": len(raw),
        "data_origin": file_origin,
        "evaluation_eligible": eligible,
        "status": file_status,
        "record_count": len(records),
        "is_pilot": is_pilot,
    }
    return records, info


def load_real_input_dir(input_dir: Path) -> dict[str, Any]:
    """Load optional real experiment files from input_dir with provenance and contract checks."""
    m0_m4_events, m0_m4_info = inspect_and_load_input_file(input_dir, "m0_m4_events.json", "events")
    q4_samples, q4_info = inspect_and_load_input_file(input_dir, "q4_presence.json", "samples")
    q5_windows, q5_info = inspect_and_load_input_file(input_dir, "q5_switch_windows.json", "windows")

    input_files_info = [m0_m4_info, q4_info, q5_info]
    source_pins = {info["name"]: info["sha256"] for info in input_files_info}

    all_real = all(info["status"] == REAL_DATA for info in input_files_info)
    any_synthetic = any(info["status"] == SYNTHETIC for info in input_files_info)
    all_eligible = all(info["evaluation_eligible"] is True for info in input_files_info)

    if any_synthetic:
        data_origin = SYNTHETIC
    elif all_real and all_eligible:
        data_origin = REAL_DATA
    else:
        data_origin = PENDING_REAL_DATA

    return {
        "data_origin": data_origin,
        "m0_m4_events": m0_m4_events,
        "m0_m4_status": m0_m4_info["status"],
        "q4_samples": q4_samples,
        "q4_status": q4_info["status"],
        "q5_windows": q5_windows,
        "q5_status": q5_info["status"],
        "input_files": input_files_info,
        "source_pins": source_pins,
        "evaluation_eligible": all_eligible,
    }


def generate_report(
    out_dir: Path,
    *,
    synthetic: bool = False,
    input_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate all report tables (CSV + MD), figures (PNG), and manifest.json."""
    if synthetic and input_dir is not None:
        raise ValueError("Specify either --synthetic or --input-dir, not both.")
    if not synthetic and input_dir is None:
        raise ValueError("Must specify either --synthetic or --input-dir.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_pins: dict[str, str | None] = {}
    input_files_manifest: list[dict[str, Any]] = []

    if synthetic:
        dataset = build_synthetic_dataset()
        m0_m4_default_status = SYNTHETIC
        q4_default_status = SYNTHETIC
        q5_default_status = SYNTHETIC
        banner = "SYNTHETIC PREVIEW - NOT FORMAL EVIDENCE (REAL DATA PENDING #416 / #425)"
    else:
        assert input_dir is not None
        dataset = load_real_input_dir(Path(input_dir))
        m0_m4_default_status = dataset["m0_m4_status"]
        q4_default_status = dataset["q4_status"]
        q5_default_status = dataset["q5_status"]
        source_pins = dataset["source_pins"]
        input_files_manifest = dataset["input_files"]
        if dataset["data_origin"] == REAL_DATA:
            banner = "DATA ORIGIN: REAL_DATA (EVALUATION-ELIGIBLE SAFE PACK)"
        elif dataset["data_origin"] == SYNTHETIC:
            banner = "DATA ORIGIN: SYNTHETIC (SIMULATION FIXTURE - NOT SAFE PACK EVIDENCE)"
        else:
            banner = f"DATA ORIGIN: {dataset['data_origin']} - UNMEASURED ITEMS MARKED PENDING_REAL_DATA / UNKNOWN"

    # 1. Table & Figure: M0..M4 Comparison
    m0_m4_rows, m0_m4_status = compute_m0_m4_table(dataset["m0_m4_events"], m0_m4_default_status)
    m0_m4_notes = [
        "Compares Baseline (RULE_ONLY) against M1..M4 model combinations across event metrics.",
        "Missing or unmeasured arms are reported as PENDING_REAL_DATA / UNKNOWN and never imputed.",
    ]
    t1_csv, t1_md = write_csv_and_md(
        out_dir,
        "table_m0_m4_comparison",
        M0_M4_COLUMNS,
        m0_m4_rows,
        "Table 1: Baseline (RULE_ONLY) vs M1-M4 Event Comparison",
        banner,
        m0_m4_notes,
    )
    f1_png = out_dir / "fig_m0_m4_comparison.png"
    f1_bytes = render_grouped_bar_chart_png(
        title="FIG 1: M0 (RULE_ONLY) VS M1-M4 EVENT METRICS",
        subtitle="ACTION MATCH RATE, FALSE HANDOFF RATE, AND ABSTENTION RATE (%)",
        banner=banner,
        categories=[r["arm_id"] for r in m0_m4_rows],
        series=[
            ("MATCH%", [_parse_pct(r["action_match_rate_pct"]) for r in m0_m4_rows]),
            ("FALSE_HO%", [_parse_pct(r["false_handoff_rate_pct"]) for r in m0_m4_rows]),
            ("ABSTAIN%", [_parse_pct(r["abstention_rate_pct"]) for r in m0_m4_rows]),
        ],
    )
    f1_png.write_bytes(f1_bytes)

    # 2. Table & Figure: Q4 Presence Accuracy
    q4_rows, q4_status = compute_q4_table(dataset["q4_samples"], q4_default_status)
    q4_notes = [
        "Q4 T/F presence evaluation across strata; UNKNOWN reviews are excluded from decided denominators.",
        "Formal r004 numbers remain pending until human T/F review and full runs complete.",
    ]
    t2_csv, t2_md = write_csv_and_md(
        out_dir,
        "table_q4_presence_accuracy",
        Q4_COLUMNS,
        q4_rows,
        "Table 2: Q4 Presence Accuracy, Precision, Recall, F1, and UNKNOWN Rate",
        banner,
        q4_notes,
    )
    f2_png = out_dir / "fig_q4_presence_accuracy.png"
    f2_bytes = render_grouped_bar_chart_png(
        title="FIG 2: Q4 PRESENCE ACCURACY AND F1 BY STRATUM",
        subtitle="DECIDED ACCURACY, PRECISION, RECALL, F1, AND TOTAL UNKNOWN RATE (%)",
        banner=banner,
        categories=[r["stratum"] for r in q4_rows],
        series=[
            ("ACC%", [_parse_pct(r["accuracy_pct"]) for r in q4_rows]),
            ("PREC%", [_parse_pct(r["precision_pct"]) for r in q4_rows]),
            ("REC%", [_parse_pct(r["recall_pct"]) for r in q4_rows]),
            ("UNK%", [_parse_pct(r["unknown_rate_pct"]) for r in q4_rows]),
        ],
    )
    f2_png.write_bytes(f2_bytes)

    # 3. Table & Figure: Q5 Switch Decision-Window Consistency
    q5_rows, q5_status = compute_q5_table(dataset["q5_windows"], q5_default_status)
    q5_notes = [
        "Q5 decision-window consistency across KEEP, HANDOFF, LOST, and ABSTAIN categories.",
        "Windows with UNKNOWN observed outcome are counted in n_unknown and excluded from agreement denominator.",
    ]
    t3_csv, t3_md = write_csv_and_md(
        out_dir,
        "table_q5_switch_consistency",
        Q5_COLUMNS,
        q5_rows,
        "Table 3: Q5 Camera Switch Decision-Window Consistency",
        banner,
        q5_notes,
    )
    f3_png = out_dir / "fig_q5_switch_consistency.png"
    f3_bytes = render_grouped_bar_chart_png(
        title="FIG 3: Q5 CAMERA SWITCH DECISION-WINDOW CONSISTENCY",
        subtitle="WINDOW AGREEMENT RATE (%) ACROSS KEEP / HANDOFF / LOST / ABSTAIN",
        banner=banner,
        categories=[r["decision_category"] for r in q5_rows],
        series=[
            ("AGREE%", [_parse_pct(r["agreement_rate_pct"]) for r in q5_rows]),
        ],
    )
    f3_png.write_bytes(f3_bytes)

    generated_paths = [
        (t1_csv, "csv"),
        (t1_md, "markdown"),
        (f1_png, "png"),
        (t2_csv, "csv"),
        (t2_md, "markdown"),
        (f2_png, "png"),
        (t3_csv, "csv"),
        (t3_md, "markdown"),
        (f3_png, "png"),
    ]

    files_manifest: list[dict[str, Any]] = []
    sha256_by_file: dict[str, str] = {}
    for path, kind in generated_paths:
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        files_manifest.append({
            "name": path.name,
            "kind": kind,
            "size_bytes": len(raw),
            "sha256": digest,
        })
        sha256_by_file[path.name] = digest

    if synthetic:
        overall_origin = SYNTHETIC
    elif (
        m0_m4_status == REAL_DATA
        and q4_status == REAL_DATA
        and q5_status == REAL_DATA
        and dataset.get("data_origin") == REAL_DATA
    ):
        overall_origin = REAL_DATA
    elif (
        m0_m4_status == SYNTHETIC
        or q4_status == SYNTHETIC
        or q5_status == SYNTHETIC
        or dataset.get("data_origin") == SYNTHETIC
    ):
        overall_origin = SYNTHETIC
    else:
        overall_origin = PENDING_REAL_DATA

    manifest = {
        "issue_ref": "#427",
        "generator": "scripts/research/generate_report_tables_and_figures.py",
        "data_origin": overall_origin,
        "real_data_status": REAL_DATA if overall_origin == REAL_DATA else PENDING_REAL_DATA,
        "table_statuses": {
            "table_m0_m4_comparison": m0_m4_status,
            "table_q4_presence_accuracy": q4_status,
            "table_q5_switch_consistency": q5_status,
        },
        "files": files_manifest,
        "sha256_by_file": sha256_by_file,
    }
    if source_pins:
        manifest["source_pins"] = source_pins
    if input_files_manifest:
        manifest["input_files"] = input_files_manifest
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--synthetic",
        action="store_true",
        help="Run on built-in deterministic synthetic fixture inputs (marks data_origin=SYNTHETIC).",
    )
    mode.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing real experiment JSON outputs (unmeasured inputs marked PENDING_REAL_DATA).",
    )
    parser.add_argument(
        "--out",
        "--output-dir",
        dest="out_dir",
        type=Path,
        required=True,
        help="Output directory for generated CSV, Markdown, PNG, and manifest.json files.",
    )
    args = parser.parse_args(argv)
    manifest = generate_report(args.out_dir, synthetic=args.synthetic, input_dir=args.input_dir)
    print(
        f"Generated {len(manifest['files'])} artifacts in {args.out_dir} "
        f"(data_origin={manifest['data_origin']}, real_data_status={manifest['real_data_status']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
