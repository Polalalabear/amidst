#!/usr/bin/env bash
# Mac-side one-click experiment orchestrator skeleton (#731 item 7 -> #732 FEAT-EXP-RUN).
# Dry-run by default (DRY_RUN=1 or --dry-run). Pass --execute to run stages.
#
# Cost rule (preregistration / #731):
#   Cumulative API spend = base USD 38.17 + new ApiGuard ledger rows
#   Hard cap             = USD 90.00 (this round estimated <= USD 47.00)
#
# Identity status: UNCONFIRMED. GT stays on scoring side only.

set -euo pipefail

DRY_RUN="${DRY_RUN:-1}"
DATAPACK_ROOT="${DATAPACK_ROOT:-local}"
OUT_DIR="${OUT_DIR:-local/evidence/exp-run-out}"
COLAB_PACK_ROOT="${COLAB_PACK_ROOT:-${OUT_DIR}/e7-colab-pack}"
RAW_ANSWER_TABLE_JSON="${RAW_ANSWER_TABLE_JSON:-}"
BASE_SPEND_USD="${BASE_SPEND_USD:-38.17}"
CAP_USD="${CAP_USD:-90.00}"
AMIDST_API_USAGE_DIR="${AMIDST_API_USAGE_DIR:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --execute) DRY_RUN=0 ;;
    --datapack-root=*) DATAPACK_ROOT="${arg#*=}" ;;
    --out-dir=*) OUT_DIR="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 [--dry-run | --execute] [--datapack-root=PATH] [--out-dir=PATH]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

run_step() {
  local label="$1"
  shift
  echo "==> [${label}]"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] $*"
  else
    "$@"
  fi
}

echo "============================================================"
echo "Amidst Experiment Pipeline Skeleton (Mac #732)"
echo "  DRY_RUN       : ${DRY_RUN}"
echo "  DATAPACK_ROOT : ${DATAPACK_ROOT}"
echo "  OUT_DIR       : ${OUT_DIR}"
echo "  USAGE_DIR     : ${AMIDST_API_USAGE_DIR:-<UNSET>}"
echo "  COST RULE     : base USD ${BASE_SPEND_USD} + new ledger rows <= USD ${CAP_USD}"
echo "  IDENTITY      : UNCONFIRMED"
echo "============================================================"

# Stage 1: Preflight & ApiGuard ledger cost budget check (reads real usage.jsonl est_cost_usd, excludes DENIED)
BUDGET_CHECK_PY='
import json, math, pathlib, sys
base = float(sys.argv[1])
cap = float(sys.argv[2])
usage_dir_raw = sys.argv[3].strip()

def load_rows(usage_path: pathlib.Path):
    if usage_path.is_file():
        ledger_file = usage_path
        usage_dir = usage_path.parent
    else:
        usage_dir = usage_path
        ledger_file = usage_dir / "usage.jsonl"
    try:
        from amidst.q1q5.api_budget import ApiGuard, GuardConfig
        if ledger_file.name == "usage.jsonl":
            return ApiGuard(GuardConfig(), usage_dir=usage_dir)._rows(), ledger_file
    except Exception:
        pass
    if not ledger_file.is_file():
        return [], ledger_file
    rows = []
    for line in ledger_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows, ledger_file

new_spend = 0.0
rows_counted = 0
denied_skipped = 0
if not usage_dir_raw:
    print("WARNING: AMIDST_API_USAGE_DIR is unset/empty; reporting 0.00 USD new ledger rows.")
else:
    p = pathlib.Path(usage_dir_raw)
    if not p.exists():
        print(f"WARNING: AMIDST_API_USAGE_DIR={p} does not exist; reporting 0.00 USD new ledger rows.")
    else:
        rows, ledger_file = load_rows(p)
        if not ledger_file.is_file():
            print(f"WARNING: ApiGuard ledger {ledger_file} not found; reporting 0.00 USD new ledger rows.")
        for r in rows:
            if r.get("outcome") == "DENIED":
                denied_skipped += 1
                continue
            val = r.get("est_cost_usd")
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val):
                new_spend += float(val)
                rows_counted += 1

total = round(base + new_spend, 4)
rem = round(cap - total, 4)
print(
    f"Budget check: base={base:.2f} + new_ledger={new_spend:.4f} "
    f"({rows_counted} charged rows, {denied_skipped} DENIED excluded) "
    f"= total={total:.4f} USD / cap={cap:.2f} USD (remaining={rem:.4f} USD)"
)
if total > cap:
    raise SystemExit(f"BUDGET_CAP_EXCEEDED: total={total:.4f} > cap={cap:.2f} USD")
'

run_step "Stage 1: Preflight & ApiGuard Ledger Budget Check" \
  "$PYTHON_BIN" -c "$BUDGET_CHECK_PY" "${BASE_SPEND_USD}" "${CAP_USD}" "${AMIDST_API_USAGE_DIR}"

# Stage 2: E6 3-segment diagnostic + automatic group selection + 12-segment formal run
echo "==> [Stage 2: E6 Diagnostic -> Auto-Select -> 12-Segment Formal]"
echo "    [PENDING PR #726 MERGE] Wire E6 auto-selection receipt + de-anchoring (#718/#721) once PR #726 merges."

# Stage 3: #672 Multi-target exploratory tracking
echo "==> [Stage 3: #672 Multi-Target Tracking (A red / B orange-red / C blue)]"
echo "    [PENDING #676 MERGE] Wire target_color pipeline once #676 merges."

# Stage 4: E7 Colab upload pack preparation & D385/D392 pre-upload gate
# Answer tables MUST be written via amidst.evaluation.e7_scoring_bridge.write_colab_answer_table
# and packs MUST pass verify_colab_pack_pre_upload before uploading to Google Drive.
if [[ -n "${RAW_ANSWER_TABLE_JSON}" ]]; then
  run_step "Stage 4a: Write Validated Colab Answer Table (D385/D392)" \
    env PYTHONPATH="src${PYTHONPATH:+:${PYTHONPATH}}" "$PYTHON_BIN" -m amidst.evaluation.e7_scoring_bridge \
      write-answer-table \
      --in "${RAW_ANSWER_TABLE_JSON}" \
      --out "${COLAB_PACK_ROOT}/scoring_only/answer_table.json"
fi
run_step "Stage 4b: Verify E7 Colab Upload Pack Pre-Upload Gate (D385/D392)" \
  env PYTHONPATH="src${PYTHONPATH:+:${PYTHONPATH}}" "$PYTHON_BIN" -m amidst.evaluation.e7_scoring_bridge \
    verify-pack \
    --pack-root "${COLAB_PACK_ROOT}"
echo "    After pre-upload gate passes, upload ${COLAB_PACK_ROOT} to Drive, run notebooks/e7_colab_decider_eval.ipynb on Colab Pro, and place e7_analysis_<date>.json under ${OUT_DIR}/e7/."

# Stage 5: AO-L zero-latency rescoring (zero paid API calls)
run_step "Stage 5: AO-L Zero-Latency Rescoring (0 USD)" \
  "$PYTHON_BIN" scripts/evaluation/rescore_aol_zero_latency.py \
    --datapack-root "${DATAPACK_ROOT}" \
    --out-json "${OUT_DIR}/aol_zero_latency_rescore.json" \
    --out-md "${OUT_DIR}/aol_zero_latency_rescore.md"

# Stage 6: Unified Analysis Generator (md + json + PNG charts)
run_step "Stage 6: Unified Analysis Generator" \
  "$PYTHON_BIN" scripts/evaluation/generate_unified_analysis.py \
    --datapack-root "${DATAPACK_ROOT}" \
    --aol-zero-latency "${OUT_DIR}/aol_zero_latency_rescore.json" \
    --out-dir "${OUT_DIR}/unified" \
    --platform "macOS-Codex"

echo "Done (DRY_RUN=${DRY_RUN})."
