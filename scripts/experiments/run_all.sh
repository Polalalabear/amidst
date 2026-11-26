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
BASE_SPEND_USD="${BASE_SPEND_USD:-38.17}"
CAP_USD="${CAP_USD:-90.00}"
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
echo "  COST RULE     : base USD ${BASE_SPEND_USD} + new ledger rows <= USD ${CAP_USD}"
echo "  IDENTITY      : UNCONFIRMED"
echo "============================================================"

# Stage 1: Preflight & cost budget check
run_step "Stage 1: Preflight & Budget Check" \
  "$PYTHON_BIN" -c "base=${BASE_SPEND_USD}; cap=${CAP_USD}; rem=round(cap-base,2); assert rem>0, 'BUDGET_CAP_EXCEEDED'; print(f'Budget OK: base={base:.2f}, cap={cap:.2f}, remaining={rem:.2f} USD')"

# Stage 2: E6 3-segment diagnostic + automatic group selection + 12-segment formal run
echo "==> [Stage 2: E6 Diagnostic -> Auto-Select -> 12-Segment Formal]"
echo "    [PENDING PR #726 MERGE] Wire E6 auto-selection receipt + de-anchoring (#718/#721) once PR #726 merges."

# Stage 3: #672 Multi-target exploratory tracking
echo "==> [Stage 3: #672 Multi-Target Tracking (A red / B orange-red / C blue)]"
echo "    [PENDING #676 MERGE] Wire target_color pipeline once #676 merges."

# Stage 4: E7 Colab upload pack preparation (see docs/evaluation/E7_COLAB_UPLOAD_PACK_SPEC_V1.md)
echo "==> [Stage 4: E7 Colab Upload Pack Prep]"
echo "    Prepare pack per docs/evaluation/E7_COLAB_UPLOAD_PACK_SPEC_V1.md (no raw GT/trajectories/visibility/depth)."
echo "    Run notebooks/e7_colab_decider_eval.ipynb on Colab Pro and place e7_analysis_<date>.json under ${OUT_DIR}/e7/."

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
