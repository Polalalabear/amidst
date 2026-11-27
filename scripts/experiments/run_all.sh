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
# E6 (#732 G4, D396/D398): paths are relative to the repo checkout that holds local/ (run from there).
E6_PHASE="${E6_PHASE:-all}"            # none | diag | select | formal | all (all = 2a + 2b + 2c)

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --execute) DRY_RUN=0 ;;
    --datapack-root=*) DATAPACK_ROOT="${arg#*=}" ;;
    --out-dir=*) OUT_DIR="${arg#*=}" ;;
    --e6-phase=*) E6_PHASE="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 [--dry-run | --execute] [--datapack-root=PATH] [--out-dir=PATH] [--e6-phase=none|diag|select|formal|all]"
      echo "  Stage 2 (E6) with --execute spends money (diagnostic K=1, then the formal 12 segments). The formal phase additionally"
      echo "  needs E6_BATCH3_APPROVED=1 (batch-3 review + user approval, prereg section 0.2)."
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

# Stage 2: E6 diagnostic (3 segments) -> automatic group selection (prereg 2.2) -> batch-3 freeze receipt -> formal 12 segments
# Spec: docs/evaluation/E6_PREREGISTRATION_DRAFT.md 2.1, 2.2, 3.1, 5, 7. Scoring/verdicts (verdict_e6, Holm IUT) are NOT run here:
# the formal outputs land in ${E6_FORMAL_OUT}/{b1,ao_orig,arms}/<case>/ for the separate scoring task.
EVIDENCE_ROOT="${EVIDENCE_ROOT:-${DATAPACK_ROOT}/evidence}"
CAMERA_CATALOG="${CAMERA_CATALOG:-${DATAPACK_ROOT}/data/live-assets-20261115/cameras.catalog.json}"
E3_ROOT="${E3_ROOT:-${EVIDENCE_ROOT}/e3-652-20261122}"
E3_CATALOG="${E3_CATALOG:-configs/evaluation/e3_live_cases_v1.json}"
E6_RECON="${E6_RECON:-${EVIDENCE_ROOT}/api-usage/RECONCILIATION_20261124.json}"
E6_DIAG_OUT="${E6_DIAG_OUT:-${EVIDENCE_ROOT}/e6-arms-k1-20261127}"
E6_RN_OLD="${E6_RN_OLD:-${EVIDENCE_ROOT}/e6-rn-old16-20261127}"
E6_FREEZE_DIR="${E6_FREEZE_DIR:-${EVIDENCE_ROOT}/e6-batch3-freeze-20261127}"
E6_FORMAL_ROOT="${E6_FORMAL_ROOT:-${EVIDENCE_ROOT}/e6-formal-20261127}"
E6_FORMAL_OUT="${E6_FORMAL_OUT:-${EVIDENCE_ROOT}/e6-formal-run-20261127}"
E6_DIAG_CASES=(E3-A1 E3-B1 E3-C1)
E6_FORMAL_CASES=(E6-S01 E6-S02 E6-S03 E6-S04 E6-S05 E6-S06 E6-S07 E6-S08 E6-S09 E6-S10 E6-S11 E6-S12)
E6_RECEIPT="${E6_FREEZE_DIR}/BATCH3_FREEZE.json"
# ledgers whose rows count as new spend for the formal gate (diagnostic ledger + the Stage 1 ledger when set)
E6_LEDGERS=("${E6_DIAG_OUT}/ledger")
[[ -n "${AMIDST_API_USAGE_DIR}" ]] && E6_LEDGERS+=("${AMIDST_API_USAGE_DIR}")

# like run_step, but stdout goes to a file (dry-run estimates; captured text is evidence for the receipt)
run_to_file() {
  local label="$1" file="$2"
  shift 2
  echo "==> [${label}] -> ${file}"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] $* > ${file}"
  else
    mkdir -p "$(dirname "${file}")"
    "$@" > "${file}"
  fi
}

e6_phase_has() { [[ "$E6_PHASE" == "all" || "$E6_PHASE" == "$1" ]]; }

echo "==> [Stage 2: E6 Diagnostic -> Auto-Select -> 12-Segment Formal]  phase=${E6_PHASE}"
case "$E6_PHASE" in none|diag|select|formal|all) ;; *) echo "bad --e6-phase: ${E6_PHASE}" >&2; exit 2 ;; esac

if e6_phase_has diag; then
  # 2a. B1 and AO_ORIG diagnostic records already exist (f4-658 runs-final-9, e5-20261123 runs-9): not rerun.
  # R-N is deterministic and free; e6_rule_neutral.py replays the old 16 corpora only (its output dir must not exist).
  if [[ -d "${E6_RN_OLD}" ]]; then
    echo "==> [Stage 2a: R-N old 16] exists, skipped: ${E6_RN_OLD}"
  else
    run_step "Stage 2a: R-N (0 USD, old 16 corpora)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_rule_neutral.py --evidence "${EVIDENCE_ROOT}" \
        --cameras "${CAMERA_CATALOG}" --out "${E6_RN_OLD}"
  fi
  # Request sizes and the USD upper bound first (no network, no key); e6_arms_run.py repeats it before the paid run.
  run_step "Stage 2a: diagnostic dry-run estimate (DEANCHOR/_HIST/_HIST_SUM, K=1)" \
    "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E3_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --cases "${E6_DIAG_CASES[@]}" --k 1 --dry-run
  # Paid K=1 diagnostic (<= USD 10, ApiGuard, own ledger under ${E6_DIAG_OUT}/ledger); existing outputs are skipped.
  extra_ledger=()
  [[ -n "${AMIDST_API_USAGE_DIR}" ]] && extra_ledger=(--extra-ledger "${AMIDST_API_USAGE_DIR}")
  run_step "Stage 2a: diagnostic paid run (K=1, 3 cases x 3 arms, <= USD 10)" \
    "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E3_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --cases "${E6_DIAG_CASES[@]}" --k 1 --paid --max-usd 10 --baseline-json "${E6_RECON}" \
      --out "${E6_DIAG_OUT}" ${extra_ledger[@]+"${extra_ledger[@]}"}
fi

if e6_phase_has select; then
  if [[ -f "${E6_RECEIPT}" ]]; then
    echo "==> [Stage 2b] frozen receipt exists, NOT re-selecting (prereg 0.2): ${E6_RECEIPT}"
  else
    # Formal dry-run estimates (K=3) go into the receipt; they need the frozen formal recording (PR #745), not any model output.
    run_to_file "Stage 2b: formal dry-run estimate, e6_arms_run.py (K=3, all pool arms)" "${E6_FREEZE_DIR}/formal_arms_dryrun.json" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --cases "${E6_FORMAL_CASES[@]}" --k 3 --dry-run
    run_to_file "Stage 2b: formal dry-run estimate, e5_run.py (AO_ORIG, K=3)" "${E6_FREEZE_DIR}/formal_ao_orig_dryrun.txt" \
      "$PYTHON_BIN" -B scripts/evaluation/e5_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --out "${E6_FREEZE_DIR}/_unused_ao_out" --usage-dir "${E6_FREEZE_DIR}/_unused_ao_ledger" \
        --cases "${E6_FORMAL_CASES[@]}" --k 3 --mode offline --budget-usd 32 --dry-run
    # B1 / AO_ORIG / R-N records are shown for information only; the rule picks among the three DEANCHOR groups.
    run_step "Stage 2b: select group (hard gate + ordered rule) and write the batch-3 freeze receipt" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_select_arm.py select \
        --source "${E3_ROOT}" "${E3_CATALOG}" "${E6_DIAG_OUT}" \
        --source "${E3_ROOT}" "${E3_CATALOG}" "${EVIDENCE_ROOT}/f4-658-20261122/runs-final-9" \
        --source "${E3_ROOT}" "${E3_CATALOG}" "${EVIDENCE_ROOT}/e5-20261123/runs-9" \
        --source "${E3_ROOT}" "${E3_CATALOG}" "${E6_RN_OLD}" \
        --formal-estimate "${E6_FREEZE_DIR}/formal_arms_dryrun.json" --ao-estimate "${E6_FREEZE_DIR}/formal_ao_orig_dryrun.txt" \
        --out "${E6_FREEZE_DIR}"
  fi
fi

if e6_phase_has formal; then
  # 2c. Formal 12 segments. Gate order: approval -> data separation -> frozen receipt + budget. Nothing is run before all pass.
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] gate: E6_BATCH3_APPROVED=1 required (currently '${E6_BATCH3_APPROVED:-unset}')"
  elif [[ "${E6_BATCH3_APPROVED:-}" != "1" ]]; then
    echo "STOPPED at the batch-3 gate: E6_BATCH3_APPROVED=1 is not set. The preregistration requires the batch-3 review of ${E6_RECEIPT}" >&2
    echo "and the user's approval in chat before the formal 12 segments are run. Nothing was run in Stage 2c." >&2
    exit 6
  fi
  run_step "Stage 2c gate: data separation (formal mode, physical artifacts)" \
    "$PYTHON_BIN" -B scripts/evaluation/check_e6_data_separation.py --mode formal --artifact-root "${E6_FORMAL_ROOT}"
  run_step "Stage 2c gate: frozen receipt + formal dry-run <= USD 32 + cumulative (D375 base ${BASE_SPEND_USD} + ledger + estimate <= ${CAP_USD})" \
    "$PYTHON_BIN" -B scripts/evaluation/e6_select_arm.py formal-gate --receipt "${E6_RECEIPT}" \
      --arms-estimate "${E6_FREEZE_DIR}/formal_arms_dryrun.json" --ao-estimate "${E6_FREEZE_DIR}/formal_ao_orig_dryrun.txt" \
      --base "${BASE_SPEND_USD}" --cap "${CAP_USD}" --out "${E6_FREEZE_DIR}/formal_gate.json" --ledger "${E6_LEDGERS[@]}"
  # Group list and ApiGuard budgets come from the receipt and the gate result (budget = the dry-run USD upper bound, in cents).
  AGENT_ARMS=(DEANCHOR)
  AO_BUDGET="<AO_ORIG budget from formal_gate.json>"
  ARMS_BUDGET="<agent arms budget from formal_gate.json>"
  if [[ -f "${E6_RECEIPT}" ]]; then
    SELECTED_AGENT="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["SELECTED_AGENT"])' "${E6_RECEIPT}")"
    [[ "${SELECTED_AGENT}" != "DEANCHOR" ]] && AGENT_ARMS+=("${SELECTED_AGENT}")
  else
    AGENT_ARMS+=("<SELECTED_AGENT, if not DEANCHOR>")
  fi
  if [[ -f "${E6_FREEZE_DIR}/formal_gate.json" ]]; then
    AO_BUDGET="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["per_group_budget_usd"]["AO_ORIG"])' "${E6_FREEZE_DIR}/formal_gate.json")"
    ARMS_BUDGET="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["agent_arms_budget_usd"])' "${E6_FREEZE_DIR}/formal_gate.json")"
  fi
  # Free groups (B1 = E3 replay script on the new recording).
  run_step "Stage 2c: B1 on the formal recording (0 USD, K=1)" \
    "$PYTHON_BIN" -B scripts/evaluation/e3_f4_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --out "${E6_FORMAL_OUT}/b1" --cases "${E6_FORMAL_CASES[@]}" --arms B1
  # R-N (zero cost): same frozen detections, seed = first ACQUIRE of the B1 run just written above (nothing else crosses). Output dir must not exist.
  if [[ -d "${E6_FORMAL_OUT}/rn" ]]; then
    echo "==> [Stage 2c: R-N formal] exists, skipped: ${E6_FORMAL_OUT}/rn"
  else
    run_step "Stage 2c: R-N on the formal recording (0 USD, RN_U + RN_N)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_rule_neutral.py --root "${E6_FORMAL_ROOT}" --b1-runs "${E6_FORMAL_OUT}/b1" \
        --cases "${E6_FORMAL_CASES[@]}" --cameras "${CAMERA_CATALOG}" --out "${E6_FORMAL_OUT}/rn"
  fi
  # Paid groups, K=3. AO_ORIG = the unchanged E5 A-open (e5_run.py); budget = the gate's USD upper bound (ApiGuard cap per invocation).
  run_step "Stage 2c: AO_ORIG (K=3, paid, offline)" \
    "$PYTHON_BIN" -B scripts/evaluation/e5_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --out "${E6_FORMAL_OUT}/ao_orig" --usage-dir "${E6_FORMAL_OUT}/ledger-ao_orig" \
      --cases "${E6_FORMAL_CASES[@]}" --k 3 --mode offline --budget-usd "${AO_BUDGET}"
  # UNKNOWN: e6_arms_run.py paid mode currently refuses anything but K=1 and E3-A1/B1/C1 (PAID_COMBINATION_REFUSED); the formal
  # K=3 paid mode on E6-S01..S12 must be added in PR #743. The call below is the intended interface and fails closed until then.
  run_step "Stage 2c: DEANCHOR${AGENT_ARMS[1]:+ + ${AGENT_ARMS[1]}} (K=3, paid)" \
    "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --cases "${E6_FORMAL_CASES[@]}" --arms "${AGENT_ARMS[@]}" --k 3 --paid --max-usd "${ARMS_BUDGET}" \
      --baseline-json "${E6_RECON}" --out "${E6_FORMAL_OUT}/arms" --extra-ledger "${E6_LEDGERS[@]}" "${E6_FORMAL_OUT}/ledger-ao_orig"
  echo "    Scoring and verdicts (verdict_e6, Holm IUT) are a separate task; inputs: ${E6_FORMAL_OUT}/{b1,rn,ao_orig,arms}/<case>/."
fi

# Stage 3: #672 Multi-target exploratory tracking
echo "==> [Stage 3: #672 Multi-Target Tracking (A red / B orange-red / C blue)]"
echo "    [BLOCKED] #676 (blue target detected but LOST; re-acquire gate only recognises red) is still OPEN; Stage 3 is not run."
echo "    Wire the target_color pipeline here only after #676 is merged and its fix is on main."

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
