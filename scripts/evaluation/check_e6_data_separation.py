"""Check E6 data separation, unique decision points, and SHA manifest integrity.

Zero-cost, offline verification for #718 (D377):
- Verifies all 16 old E3 cases match committed catalogs byte-for-byte.
- Verifies the 3 diagnostic cases are strictly disjoint from the 12 formal cases
  (case_id, family_id, and SHA-256).
- Verifies the 12 formal cases reuse zero old E3 families or old opening coordinates.
- Verifies 12 distinct openings, 6 similar / 6 non-similar balance,
  unique valid decision points >= 40 (no duplicate dp_id or per-case timestamp,
  finite and within [0, duration_s)), and effective independent units >= 8.
- Supports:
  - --mode draft: pre-recording manifest check (still rejects FROZEN with null/missing SHA).
  - --mode formal --artifact-root <dir>: mandatory post-recording freeze gate.
    Requires --artifact-root, hashes and verifies every formal case_path and gt_path
    byte-for-byte on disk, loads each frozen GT A-log, verifies every actual DP's tick
    matches the 5 Hz clock (t_actual_s), lies within recording duration, has complete
    3.0 s evaluation window GT rows, and matches the GT-derived gt_regime
    (VISIBLE / FULL_BLIND / TRUE_DEPARTURE). Only scorable unique DPs count toward >= 40.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
OLD_E3_OPENING_COORDS = {(-10.0, -0.4), (4.0, 1.0)}
VALID_GT_REGIMES = {"VISIBLE", "FULL_BLIND", "TRUE_DEPARTURE"}
DEFAULT_FPS_HZ = 5
WINDOW_S = 3.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _coord_key(xy: list[float] | tuple[float, float]) -> tuple[float, float]:
    return (round(float(xy[0]), 3), round(float(xy[1]), 3))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_gt_ticks_by_index(gt_doc: Any, cid: str, errors: list[str]) -> dict[int, dict[str, Any]] | None:
    rows = gt_doc.get("ticks") if isinstance(gt_doc, dict) else gt_doc
    if not isinstance(rows, list) or len(rows) == 0:
        errors.append(f"FORMAL_GT_MISSING_TICKS: {cid} has no GT ticks array")
        return None
    by_tick: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("tick"), int) or isinstance(row.get("tick"), bool):
            errors.append(f"FORMAL_GT_INVALID_TICK_ROW: {cid}")
            return None
        t = row["tick"]
        if t in by_tick:
            errors.append(f"FORMAL_GT_DUPLICATE_TICK: {cid} tick={t}")
            return None
        by_tick[t] = row
    return by_tick


def _derive_gt_regime(
    *,
    gt_by_tick: dict[int, dict[str, Any]],
    start_tick: int,
    window_ticks: int,
    target_id: str,
) -> tuple[str | None, str | None]:
    any_visible = False
    any_present = False
    for tk in range(start_tick, start_tick + window_ticks):
        row = gt_by_tick.get(tk)
        if row is None:
            return None, f"missing GT tick {tk} in [{start_tick}, {start_tick + window_ticks})"
        actors = row.get("actors")
        if not isinstance(actors, list):
            return None, f"GT tick {tk} missing actors list"
        target = next((a for a in actors if isinstance(a, dict) and a.get("id") == target_id), None)
        if target is None:
            return None, f"GT tick {tk} missing target actor {target_id!r}"
        present = bool(target.get("present"))
        vis = target.get("gt_visible") or []
        if not isinstance(vis, list):
            return None, f"GT tick {tk} invalid gt_visible"
        if present:
            any_present = True
            if len(vis) > 0:
                any_visible = True
    if any_visible:
        return "VISIBLE", None
    if not any_present:
        return "TRUE_DEPARTURE", None
    return "FULL_BLIND", None


def _validate_decision_points(
    *,
    cid: str,
    dps: Any,
    duration_s: Any,
    time_key: str,
    require_formal_fields: bool,
    fps_hz: int,
    gt_by_tick: dict[int, dict[str, Any]] | None,
    target_id: str,
    global_dp_ids: set[str],
    errors: list[str],
) -> int:
    if not isinstance(duration_s, (int, float)) or isinstance(duration_s, bool) or not math.isfinite(duration_s) or duration_s <= 0:
        errors.append(f"FORMAL_INVALID_DURATION: {cid} duration={duration_s!r}")
        return 0
    if not isinstance(dps, list) or len(dps) < 1:
        errors.append(f"FORMAL_NO_DECISION_POINTS: {cid}")
        return 0

    case_times: set[float] = set()
    case_ticks: set[int] = set()
    valid_unique = 0
    max_ticks = int(round(float(duration_s) * fps_hz))
    window_ticks = int(round(WINDOW_S * fps_hz))

    for idx, dp in enumerate(dps):
        if not isinstance(dp, dict):
            errors.append(f"FORMAL_DP_NOT_DICT: {cid}[{idx}]")
            continue
        dp_id = dp.get("dp_id")
        if not isinstance(dp_id, str) or not dp_id.strip():
            errors.append(f"FORMAL_DP_INVALID_ID: {cid}[{idx}]")
            continue
        if dp_id in global_dp_ids:
            errors.append(f"FORMAL_DP_DUPLICATE_ID: {dp_id}")
            continue

        t_val = dp.get(time_key)
        if not isinstance(t_val, (int, float)) or isinstance(t_val, bool) or not math.isfinite(t_val):
            errors.append(f"FORMAL_DP_INVALID_TIME: {dp_id} {time_key}={t_val!r}")
            continue
        if t_val < 0.0 or t_val >= float(duration_s):
            errors.append(f"FORMAL_DP_TIME_OUT_OF_RANGE: {dp_id} {time_key}={t_val} duration={duration_s}")
            continue
        t_key = round(float(t_val), 3)
        if t_key in case_times:
            errors.append(f"FORMAL_DP_DUPLICATE_TIME: {cid} {time_key}={t_val}")
            continue

        if require_formal_fields:
            regime = dp.get("gt_regime")
            if regime not in VALID_GT_REGIMES:
                errors.append(f"FORMAL_DP_INVALID_REGIME: {dp_id} gt_regime={regime!r}")
                continue
            tick = dp.get("tick")
            if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0:
                errors.append(f"FORMAL_DP_INVALID_TICK: {dp_id} tick={tick!r}")
                continue
            if tick >= max_ticks or (tick + window_ticks) > max_ticks:
                errors.append(
                    f"FORMAL_DP_TICK_OUT_OF_RANGE: {dp_id} tick={tick} window={window_ticks} max_ticks={max_ticks}"
                )
                continue
            expected_t_s = tick / float(fps_hz)
            if abs(float(t_val) - expected_t_s) > 1e-3:
                errors.append(
                    f"FORMAL_DP_TICK_TIME_MISMATCH: {dp_id} tick={tick} ({expected_t_s}s) != {time_key}={t_val}s"
                )
                continue
            if tick in case_ticks:
                errors.append(f"FORMAL_DP_DUPLICATE_TICK: {cid} tick={tick}")
                continue
            if gt_by_tick is None:
                errors.append(f"FORMAL_DP_UNVERIFIED_GT: {dp_id} missing loaded GT ticks")
                continue
            derived_regime, gt_err = _derive_gt_regime(
                gt_by_tick=gt_by_tick,
                start_tick=tick,
                window_ticks=window_ticks,
                target_id=target_id,
            )
            if gt_err is not None:
                errors.append(f"FORMAL_DP_GT_WINDOW_INVALID: {dp_id} {gt_err}")
                continue
            if derived_regime != regime:
                errors.append(
                    f"FORMAL_DP_REGIME_MISMATCH: {dp_id} declared={regime} gt_derived={derived_regime}"
                )
                continue
            case_ticks.add(tick)

        global_dp_ids.add(dp_id)
        case_times.add(t_key)
        valid_unique += 1

    return valid_unique


def validate_e6_spec(
    spec: dict[str, Any],
    e3_base_catalog: dict[str, Any],
    e3_ext_catalog: dict[str, Any],
    *,
    mode: str = "draft",
    artifact_root: Path | None = None,
) -> list[str]:
    if mode not in ("draft", "formal"):
        return [f"INVALID_MODE: {mode!r}"]

    errors: list[str] = []
    fps_hz = int(spec.get("capture_spec", {}).get("fps_hz", DEFAULT_FPS_HZ))

    if mode == "formal":
        if artifact_root is None:
            errors.append("FORMAL_ARTIFACT_ROOT_REQUIRED: --mode formal requires --artifact-root")
        elif not artifact_root.is_dir():
            errors.append(f"FORMAL_ARTIFACT_ROOT_MISSING: {artifact_root}")

    # 1. Build ground-truth lookup of the 16 old E3 cases from committed catalogs
    catalog_old: dict[str, dict[str, str]] = {}
    for c in e3_base_catalog.get("cases", []):
        catalog_old[c["case_id"]] = {
            "case_sha256": c["case_sha256"],
            "gt_sha256": c["gt_sha256"],
        }
    for c in e3_ext_catalog.get("cases", []):
        catalog_old[c["case_id"]] = {
            "case_sha256": c["case_sha256"],
            "gt_sha256": c["gt_sha256"],
        }

    old_cases = spec.get("old_e3_cases", [])
    if len(old_cases) != 16:
        errors.append(f"OLD_E3_COUNT: expected 16 old E3 cases, got {len(old_cases)}")

    old_ids: set[str] = set()
    old_families: set[str] = set()
    old_shas: set[str] = set()
    for c in old_cases:
        cid = c.get("case_id", "")
        old_ids.add(cid)
        old_families.add(c.get("family_id", ""))
        if cid not in catalog_old:
            errors.append(f"OLD_E3_UNKNOWN_CASE: {cid}")
            continue
        for key in ("case_sha256", "gt_sha256"):
            sha = c.get(key, "")
            expected = catalog_old[cid][key]
            if sha != expected:
                errors.append(f"OLD_E3_SHA_MISMATCH: {cid}.{key} expected {expected} got {sha}")
            old_shas.add(sha)

    if old_ids != set(catalog_old.keys()):
        missing = sorted(set(catalog_old.keys()) - old_ids)
        extra = sorted(old_ids - set(catalog_old.keys()))
        errors.append(f"OLD_E3_SET_MISMATCH: missing={missing} extra={extra}")

    # 2. Validate 3 diagnostic cases
    diag_cases = spec.get("diagnostic_cases", [])
    if len(diag_cases) != 3:
        errors.append(f"DIAG_COUNT: expected 3 diagnostic cases, got {len(diag_cases)}")

    diag_ids: set[str] = set()
    diag_families: set[str] = set()
    diag_shas: set[str] = set()
    for c in diag_cases:
        cid = c.get("case_id", "")
        fid = c.get("family_id", "")
        if cid in diag_ids:
            errors.append(f"DIAG_DUPLICATE_ID: {cid}")
        diag_ids.add(cid)
        diag_families.add(fid)
        for key in ("case_sha256", "gt_sha256"):
            sha = c.get(key)
            if not isinstance(sha, str) or not HEX64_RE.match(sha):
                errors.append(f"DIAG_INVALID_SHA: {cid}.{key}={sha!r}")
            else:
                diag_shas.add(sha)
        if cid in catalog_old:
            for key in ("case_sha256", "gt_sha256"):
                if c.get(key) != catalog_old[cid][key]:
                    errors.append(f"DIAG_SHA_MISMATCH_E3: {cid}.{key}")

    # 3. Validate 12 formal cases
    formal_cases = spec.get("formal_cases", [])
    if len(formal_cases) != 12:
        errors.append(f"FORMAL_COUNT: expected 12 formal cases, got {len(formal_cases)}")

    formal_ids: set[str] = set()
    formal_families: set[str] = set()
    formal_openings: set[tuple[float, float]] = set()
    formal_shas: set[str] = set()
    global_dp_ids: set[str] = set()
    similar_count = 0
    nonsimilar_count = 0
    total_unique_valid_dps = 0

    for c in formal_cases:
        cid = c.get("case_id", "")
        fid = c.get("family_id", "")
        if cid in formal_ids:
            errors.append(f"FORMAL_DUPLICATE_ID: {cid}")
        formal_ids.add(cid)

        if cid in diag_ids:
            errors.append(f"LEAK_DIAG_IN_FORMAL_ID: {cid}")
        if cid in old_ids:
            errors.append(f"LEAK_OLD_IN_FORMAL_ID: {cid}")

        if fid in diag_families:
            errors.append(f"LEAK_DIAG_FAMILY_IN_FORMAL: {cid} uses {fid}")
        if fid in old_families:
            errors.append(f"LEAK_OLD_FAMILY_IN_FORMAL: {cid} uses {fid}")
        formal_families.add(fid)

        xy = c.get("start_xy")
        if not isinstance(xy, list) or len(xy) != 2:
            errors.append(f"FORMAL_INVALID_START_XY: {cid}")
        else:
            ck = _coord_key(xy)
            if ck in OLD_E3_OPENING_COORDS:
                errors.append(f"FORMAL_REUSES_OLD_OPENING: {cid} start_xy={xy}")
            if ck in formal_openings:
                errors.append(f"FORMAL_DUPLICATE_OPENING: {cid} start_xy={xy}")
            formal_openings.add(ck)

        if c.get("has_similar_distractor") is True:
            similar_count += 1
        elif c.get("has_similar_distractor") is False:
            nonsimilar_count += 1
        else:
            errors.append(f"FORMAL_MISSING_SIMILAR_FLAG: {cid}")

        gt_status = c.get("actual_gt_status")
        if mode == "formal" and gt_status != "FROZEN":
            errors.append(f"FORMAL_NOT_FROZEN: {cid} actual_gt_status={gt_status!r}")

        # Verify SHAs and (in formal mode) load & verify physical artifacts on disk
        gt_by_tick: dict[int, dict[str, Any]] | None = None
        target_id = str(c.get("target_actor", "T"))
        require_shas = mode == "formal" or gt_status == "FROZEN"

        for key, path_key in (("case_sha256", "case_path"), ("gt_sha256", "gt_path")):
            sha = c.get(key)
            if sha is None:
                if require_shas:
                    errors.append(f"FORMAL_MISSING_SHA: {cid}.{key} required when mode={mode} status={gt_status}")
                continue
            if not isinstance(sha, str) or not HEX64_RE.match(sha):
                errors.append(f"FORMAL_INVALID_SHA: {cid}.{key}={sha!r}")
                continue
            if sha in old_shas:
                errors.append(f"FORMAL_SHA_COLLIDES_OLD_E3: {cid}.{key}={sha}")
            if sha in diag_shas:
                errors.append(f"FORMAL_SHA_COLLIDES_DIAG: {cid}.{key}={sha}")
            if sha in formal_shas:
                errors.append(f"FORMAL_SHA_DUPLICATE: {cid}.{key}={sha}")
            formal_shas.add(sha)

            if mode == "formal":
                rel = c.get(path_key)
                if not isinstance(rel, str) or not rel.strip():
                    errors.append(f"FORMAL_MISSING_PATH: {cid}.{path_key}")
                    continue
                if artifact_root is None or not artifact_root.is_dir():
                    continue
                target = artifact_root / rel
                if not target.is_file():
                    errors.append(f"FORMAL_ARTIFACT_MISSING: {cid}.{path_key}={target}")
                    continue
                actual_sha = _sha256_file(target)
                if actual_sha != sha:
                    errors.append(f"FORMAL_ARTIFACT_SHA_MISMATCH: {cid}.{path_key} expected {sha} got {actual_sha}")
                    continue
                try:
                    loaded = _load_json(target)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"FORMAL_ARTIFACT_INVALID_JSON: {cid}.{path_key}: {exc}")
                    continue
                if key == "gt_sha256":
                    gt_by_tick = _extract_gt_ticks_by_index(loaded, cid, errors)

        # Validate decision points (planned in draft mode; frozen GT-verified in formal mode)
        if mode == "formal":
            total_unique_valid_dps += _validate_decision_points(
                cid=cid,
                dps=c.get("actual_decision_points"),
                duration_s=c.get("actual_duration_s"),
                time_key="t_actual_s",
                require_formal_fields=True,
                fps_hz=fps_hz,
                gt_by_tick=gt_by_tick,
                target_id=target_id,
                global_dp_ids=global_dp_ids,
                errors=errors,
            )
        else:
            total_unique_valid_dps += _validate_decision_points(
                cid=cid,
                dps=c.get("planned_decision_points"),
                duration_s=c.get("planned_duration_s"),
                time_key="t_plan_s",
                require_formal_fields=False,
                fps_hz=fps_hz,
                gt_by_tick=None,
                target_id=target_id,
                global_dp_ids=global_dp_ids,
                errors=errors,
            )

    if similar_count != 6 or nonsimilar_count != 6:
        errors.append(
            f"FORMAL_SIMILAR_BALANCE: expected 6 similar / 6 non-similar, got {similar_count}/{nonsimilar_count}"
        )

    thresholds = spec.get("thresholds", {})
    min_dps = int(thresholds.get("min_decision_points", 40))
    min_units = int(thresholds.get("min_effective_units", 8))

    if total_unique_valid_dps < min_dps:
        errors.append(f"FORMAL_DP_BELOW_MIN: unique_valid={total_unique_valid_dps} < min={min_dps}")
    if len(formal_families) < min_units:
        errors.append(
            f"FORMAL_UNITS_BELOW_MIN: effective_units={len(formal_families)} < min={min_units}"
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check E6 data separation and SHA manifest.")
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("configs/evaluation/e6_scenarios_spec_v1.json"),
    )
    parser.add_argument(
        "--e3-base",
        type=Path,
        default=Path("configs/evaluation/e3_live_cases_v1.json"),
    )
    parser.add_argument(
        "--e3-ext",
        type=Path,
        default=Path("configs/evaluation/e3_reappearances_v1.json"),
    )
    parser.add_argument(
        "--mode",
        choices=("draft", "formal"),
        default="draft",
        help="draft checks pre-recording spec; formal enforces physical artifact_root SHA and GT tick/regime verification.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=None,
        help="Required in formal mode: root directory containing case_path and gt_path files to hash and verify.",
    )
    args = parser.parse_args(argv)

    spec = _load_json(args.spec)
    e3_base = _load_json(args.e3_base)
    e3_ext = _load_json(args.e3_ext)
    errors = validate_e6_spec(
        spec,
        e3_base,
        e3_ext,
        mode=args.mode,
        artifact_root=args.artifact_root,
    )
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    formal_cases = spec["formal_cases"]
    dp_key = "actual_decision_points" if args.mode == "formal" else "planned_decision_points"
    n_dps = sum(len(c.get(dp_key) or []) for c in formal_cases)
    n_units = len({c["family_id"] for c in formal_cases})
    print(
        f"PASS: E6 data separation verified (mode={args.mode}, old_e3=16, diag=3, formal=12, "
        f"unique_dps={n_dps}, effective_units={n_units}, similar=6/6)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
