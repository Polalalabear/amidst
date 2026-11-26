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

# Stage 1: Preflight & ApiGuard ledger cost budget check
BUDGET_CHECK_PY='
import csv, json, os, pathlib, sys
base = float(sys.argv[1])
cap = float(sys.argv[2])
usage_dir_raw = sys.argv[3].strip()
cost_keys = ("cost_usd", "estimated_cost_usd", "total_cost_usd", "usd", "cost")

def extract_cost(obj):
    if not isinstance(obj, dict):
        return 0.0
    for k in cost_keys:
        v = obj.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0

new_spend = 0.0
rows_counted = 0
if not usage_dir_raw:
    print("WARNING: AMIDST_API_USAGE_DIR is unset/empty; reporting 0.00 USD new ledger rows.")
else:
    p = pathlib.Path(usage_dir_raw)
    if not p.exists():
        print(f"WARNING: AMIDST_API_USAGE_DIR={p} does not exist; reporting 0.00 USD new ledger rows.")
    else:
        files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in (".jsonl", ".json", ".csv"))
        if not files:
            print(f"WARNING: AMIDST_API_USAGE_DIR={p} has no .jsonl/.json/.csv ledger files; reporting 0.00 USD new ledger rows.")
        for fp in files:
            suf = fp.suffix.lower()
            if suf == ".jsonl":
                for line in fp.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    new_spend += extract_cost(json.loads(line))
                    rows_counted += 1
            elif suf == ".json":
                doc = json.loads(fp.read_text(encoding="utf-8"))
                items = doc if isinstance(doc, list) else (doc.get("rows") or doc.get("entries") or [doc])
                for item in items:
                    new_spend += extract_cost(item)
                    rows_counted += 1
            elif suf == ".csv":
                with fp.open("r", encoding="utf-8", newline="") as fh:
                    for row in csv.DictReader(fh):
                        new_spend += extract_cost(row)
                        rows_counted += 1

total = round(base + new_spend, 4)
rem = round(cap - total, 4)
print(f"Budget check: base={base:.2f} + new_ledger={new_spend:.4f} ({rows_counted} rows) = total={total:.4f} USD / cap={cap:.2f} USD (remaining={rem:.4f} USD)")
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
