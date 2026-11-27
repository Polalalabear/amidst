#!/usr/bin/env bash
# Mac-side one-click experiment orchestrator skeleton (#731 item 7 -> #732 FEAT-EXP-RUN).
# Dry-run by default (DRY_RUN=1 or --dry-run). Pass --execute to run stages.
#
# Cost rule (preregistration / #731):
#   Cumulative API spend = base USD 38.17 + new ApiGuard ledger rows
#   Hard cap             = USD 90.00 (this round estimated <= USD 47.00)
#
# Identity status: UNCONFIRMED. GT stays on scoring side only.

set -Eeuo pipefail

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
E6_PHASE="${E6_PHASE:-all}"            # none|diag|detect|select|formal|verdict|ablation|all (all = 2a, detect, 2b, 2c, 2d, 2e)

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --execute) DRY_RUN=0 ;;
    --datapack-root=*) DATAPACK_ROOT="${arg#*=}" ;;
    --out-dir=*) OUT_DIR="${arg#*=}" ;;
    --e6-phase=*) E6_PHASE="${arg#*=}" ;;
    -h|--help)
      echo "Usage: $0 [--dry-run | --execute] [--datapack-root=PATH] [--out-dir=PATH] [--e6-phase=none|diag|detect|select|formal|verdict|ablation|all]"
      echo "  Stage 2 (E6) with --execute spends money (diagnostic K=1, formal 12 segments, ablations; D402/D403, cap USD 90)."
      echo "  runs through the mechanical batch-3 gate (e6_select_arm.py verify-freeze, exit 6 on failure); E6_STOP_AT_BATCH3=1 stops after it."
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
strict = len(sys.argv) > 4 and sys.argv[4] == "1"   # --execute: a missing ledger must stop the run, not count as 0 USD

def missing(msg):
    if strict:
        raise SystemExit("LEDGER_REQUIRED: " + msg)
    print("WARNING: " + msg + "; reporting 0.00 USD new ledger rows.")

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
    missing("AMIDST_API_USAGE_DIR is unset/empty")
else:
    p = pathlib.Path(usage_dir_raw)
    if not p.exists():
        missing(f"AMIDST_API_USAGE_DIR={p} does not exist")
    else:
        rows, ledger_file = load_rows(p)
        if not ledger_file.is_file():
            missing(f"ApiGuard ledger {ledger_file} not found (create an empty usage.jsonl for a fresh ledger)")
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
  "$PYTHON_BIN" -c "$BUDGET_CHECK_PY" "${BASE_SPEND_USD}" "${CAP_USD}" "${AMIDST_API_USAGE_DIR}" "$([[ "$DRY_RUN" == "1" ]] && echo 0 || echo 1)"

# Stage 2: E6 diagnostic (3 segments) -> automatic group selection (prereg 2.2) -> batch-3 freeze receipt -> formal 12 segments
# Spec: docs/evaluation/E6_PREREGISTRATION_DRAFT.md 2.1, 2.2, 3.1, 5, 7. Scoring/verdicts (verdict_e6, Holm IUT) are NOT run here:
# one-command run (D402/D403): --execute --e6-phase=all. Outputs: ${E6_FORMAL_OUT}/{b1,rn,ao_orig,arms,verdict,ablation-*}, STATUS.json.
# Resume: every step skips finished outputs and never overwrites; a failed hard step writes STATUS.json and stops (rerun the same command).
EVIDENCE_ROOT="${EVIDENCE_ROOT:-${DATAPACK_ROOT}/evidence}"
CAMERA_CATALOG="${CAMERA_CATALOG:-${DATAPACK_ROOT}/data/live-assets-20261115/cameras.catalog.json}"
E3_ROOT="${E3_ROOT:-${EVIDENCE_ROOT}/e3-652-20261122}"
E3_CATALOG="${E3_CATALOG:-configs/evaluation/e3_live_cases_v1.json}"
E6_RECON="${E6_RECON:-${EVIDENCE_ROOT}/api-usage/RECONCILIATION_20261124.json}"
E6_DIAG_OUT="${E6_DIAG_OUT:-${EVIDENCE_ROOT}/e6-arms-k1-20261127}"
E6_RN_OLD="${E6_RN_OLD:-${EVIDENCE_ROOT}/e6-rn-old16-20261127}"
E6_FREEZE_DIR="${E6_FREEZE_DIR:-${EVIDENCE_ROOT}/e6-batch3-freeze-20261127}"
E6_RECORD_ROOT="${E6_RECORD_ROOT:-${EVIDENCE_ROOT}/e6-formal-20261127}"         # frozen recording (wire, pixels, case, GT): read-only
E6_FORMAL_ROOT="${E6_FORMAL_ROOT:-${EVIDENCE_ROOT}/e6-formal-det-20261127}"      # inference-side root: wire clones + pixels + rgb/ + indexes/ (no GT)
E6_MODELS="${E6_MODELS:-${DATAPACK_ROOT}/data/demo-owned-v1/models/rtdetr}"
E6_RUNTIME_DEPS="${E6_RUNTIME_DEPS:-${DATAPACK_ROOT}/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps}"
E6_FORMAL_OUT="${E6_FORMAL_OUT:-${EVIDENCE_ROOT}/e6-formal-run-20261127}"
E6_DIAG_CASES=(E3-A1 E3-B1 E3-C1)
E6_FORMAL_CASES=(E6-S01 E6-S02 E6-S03 E6-S04 E6-S05 E6-S06 E6-S07 E6-S08 E6-S09 E6-S10 E6-S11 E6-S12)
E6_RECEIPT="${E6_FREEZE_DIR}/BATCH3_FREEZE.json"

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
E6_FROZEN_SPEC="${E6_FROZEN_SPEC:-configs/evaluation/e6_scenarios_frozen_v1.json}"
E6_STEP=""
# Diagnostic scoring sources shared by select and verify-freeze (non-pool arms are information only).
E6_SOURCES=(
  --source "${E3_ROOT}" "${E3_CATALOG}" "${E6_DIAG_OUT}"
  --source "${E3_ROOT}" "${E3_CATALOG}" "${EVIDENCE_ROOT}/f4-658-20261122/runs-final-9"
  --source "${E3_ROOT}" "${E3_CATALOG}" "${EVIDENCE_ROOT}/e5-20261123/runs-9"
  --source "${E3_ROOT}" "${E3_CATALOG}" "${E6_RN_OLD}"
)

# STATUS.json (resume + audit): one entry per step. Execute mode only.
e6_status() {   # state step [detail]
  [[ "$DRY_RUN" == "1" ]] && return 0
  mkdir -p "${E6_FORMAL_OUT}"
  "$PYTHON_BIN" -c '
import json, sys, pathlib, datetime
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()) if p.exists() else {"steps": {}}
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d["steps"][sys.argv[3]] = {"state": sys.argv[2], "at": now, "detail": sys.argv[4]}
d["last"] = {"step": sys.argv[3], "state": sys.argv[2], "at": now}
p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")' "${E6_FORMAL_OUT}/STATUS.json" "$1" "$2" "${3:-}"
}
e6_on_error() {  # ERR trap: record where a hard step failed (set -e then stops the script)
  local rc=$1
  trap - ERR
  [[ -n "${E6_STEP}" ]] && e6_status FAILED "${E6_STEP}" "exit ${rc}; fix the cause and rerun the same command (finished outputs are skipped)" || true
  return "$rc"
}
trap 'e6_on_error $?' ERR

# hard step: stop the run on failure, STATUS.json says where
e6_step() {   # label cmd...
  E6_STEP="$1"; shift
  echo "==> [${E6_STEP}]"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] $*"
  else
    e6_status RUNNING "${E6_STEP}"
    "$@"
    e6_status DONE "${E6_STEP}"
  fi
}
# soft step (exploratory): a failure is recorded and the run goes on
e6_soft_step() {   # label cmd...
  local label="$1"; shift
  echo "==> [${label}] (soft)"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] $*"
  elif "$@"; then
    e6_status DONE "${label}"
  else
    e6_status SOFT_FAILED "${label}" "exit $?; exploratory step, run continues"
    echo "    SOFT_FAILED: ${label}" >&2
    return 1
  fi
}
e6_soft_step_to_file() {   # label file cmd... (stdout -> file; failure is soft)
  local label="$1" file="$2"; shift 2
  echo "==> [${label}] -> ${file} (soft)"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    [DRY-RUN] $* > ${file}"
  elif "$@" > "${file}"; then
    e6_status DONE "${label}"
  else
    e6_status SOFT_FAILED "${label}" "exit $?; exploratory step, run continues"
    echo "    SOFT_FAILED: ${label}" >&2
    return 1
  fi
}
json_get() {   # file dotted.key -> value
  "$PYTHON_BIN" -c 'import json,sys
d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d[k]
print(d)' "$1" "$2"
}
count_files() { find "$1" -name "$2" 2>/dev/null | wc -l | tr -d " "; }
e6_complete() { [[ -f "$1/STATUS.json" ]] && grep -q '"COMPLETE"' "$1/STATUS.json"; }
# ledgers whose rows count as new spend: diagnostic + Stage 1 ledger (required), plus every formal ledger that exists by now
e6_refresh_ledgers() {
  E6_LEDGERS=("${E6_DIAG_OUT}/ledger")
  [[ -n "${AMIDST_API_USAGE_DIR}" ]] && E6_LEDGERS+=("${AMIDST_API_USAGE_DIR}")
  local d
  for d in "${E6_FORMAL_OUT}/ledger-ao_orig" "${E6_FORMAL_OUT}/arms/ledger" "${E6_FORMAL_OUT}"/ablation-*/ledger; do
    [[ -d "$d" ]] && E6_LEDGERS+=("$d")
  done
  return 0
}

echo "==> [Stage 2: E6 Diagnostic -> Auto-Select -> 12-Segment Formal]  phase=${E6_PHASE}"
case "$E6_PHASE" in none|diag|detect|select|formal|verdict|ablation|all) ;; *) echo "bad --e6-phase: ${E6_PHASE}" >&2; exit 2 ;; esac

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

if e6_phase_has detect; then
  # Zero-cost local detection (RT-DETR R18, MPS) on the frozen recording: the SAME producer and parameters as E3 (e3_cases/index.py),
  # output = RGB PNGs + detection index every group reads. Trial one segment first: ... e6_detect_formal.py ... --cases E6-S01
  # Needs torch 2.6.0 / torchvision 0.21.0 (E6_RUNTIME_DEPS on PYTHONPATH of the child). Stops when free disk < 5 GiB.
  run_step "Stage 2-det: formal RGB + detection index (E3 pipeline, 0 USD, local)" \
    "$PYTHON_BIN" -B scripts/evaluation/e6_detect_formal.py --recording "${E6_RECORD_ROOT}" --out "${E6_FORMAL_ROOT}" \
      --models "${E6_MODELS}" --runtime-deps "${E6_RUNTIME_DEPS}" --reference-index "${E3_ROOT}/indexes/E3-A1/detection_index.json"
fi

if e6_phase_has select; then
  if [[ -f "${E6_RECEIPT}" ]]; then
    echo "==> [Stage 2b] frozen receipt exists, NOT re-selecting (prereg 0.2): ${E6_RECEIPT}"
  else
    # Formal dry-run estimates (K=3) go into the receipt; they need the detection root above (frozen pixels + index), not any model output.
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
        "${E6_SOURCES[@]}" \
        --formal-estimate "${E6_FREEZE_DIR}/formal_arms_dryrun.json" --ao-estimate "${E6_FREEZE_DIR}/formal_ao_orig_dryrun.txt" \
        --out "${E6_FREEZE_DIR}"
  fi
fi

if e6_phase_has formal; then
  # 2c. Formal 12 segments. D402: the batch-3 review is a MECHANICAL gate (user's advance approval of the budget, #93 D402):
  # `e6_select_arm.py verify-freeze` recomputes the selection and compares the receipt field by field, checks prompt/config SHA-256 and
  # the commit, runs check_e6_data_separation.py --mode formal, and checks the Agent dry-run <= USD 32 and cumulative <= USD 90.
  # Any failure -> exit 6 here and nothing formal runs. E6_STOP_AT_BATCH3=1 stops after the gate passes (to look first).
  e6_refresh_ledgers
  if [[ -f "${E6_FREEZE_DIR}/VERIFY_FREEZE.json" && -f "${E6_FREEZE_DIR}/formal_gate.json" ]] \
     && "$PYTHON_BIN" -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("ok") else 1)' "${E6_FREEZE_DIR}/VERIFY_FREEZE.json" 2>/dev/null; then
    echo "==> [Batch-3 gate] already passed (resume): ${E6_FREEZE_DIR}/VERIFY_FREEZE.json"
  else
    E6_STEP="Batch-3 mechanical gate (verify-freeze)"
    echo "==> [${E6_STEP}]"
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "    [DRY-RUN] verify-freeze --receipt ${E6_RECEIPT} ... (exit 6 on any failed check; E6_STOP_AT_BATCH3=${E6_STOP_AT_BATCH3:-0})"
    else
      e6_status RUNNING "${E6_STEP}"
      if ! "$PYTHON_BIN" -B scripts/evaluation/e6_select_arm.py verify-freeze --receipt "${E6_RECEIPT}" "${E6_SOURCES[@]}" \
            --arms-estimate "${E6_FREEZE_DIR}/formal_arms_dryrun.json" --ao-estimate "${E6_FREEZE_DIR}/formal_ao_orig_dryrun.txt" \
            --artifact-root "${E6_RECORD_ROOT}" --frozen-spec "${E6_FROZEN_SPEC}" --base "${BASE_SPEND_USD}" --cap "${CAP_USD}" \
            --out "${E6_FREEZE_DIR}/formal_gate.json" --ledger "${E6_LEDGERS[@]}"; then
        e6_status BATCH3_GATE_FAILED "${E6_STEP}" "see ${E6_FREEZE_DIR}/VERIFY_FREEZE.json"
        echo "STOPPED at the batch-3 gate (exit 6): see ${E6_FREEZE_DIR}/VERIFY_FREEZE.json. Nothing formal was run." >&2
        trap - ERR
        exit 6
      fi
      e6_status DONE "${E6_STEP}"
    fi
  fi
  if [[ "${E6_STOP_AT_BATCH3:-0}" == "1" && "$DRY_RUN" != "1" ]]; then
    e6_status STOPPED_AT_BATCH3 "E6_STOP_AT_BATCH3=1" "gate passed; rerun without E6_STOP_AT_BATCH3 to continue"
    echo "Batch-3 gate PASSED; stopping because E6_STOP_AT_BATCH3=1. Rerun the same command without it to continue (resumes)."
    exit 0
  fi
  # Group list and ApiGuard budgets come from the receipt and the gate result (budget = the dry-run USD upper bound, in cents).
  AGENT_ARMS=(DEANCHOR)
  SELECTED_AGENT="<SELECTED_AGENT>"
  AO_BUDGET="<AO_ORIG budget from formal_gate.json>"
  ARMS_BUDGET="<agent arms budget from formal_gate.json>"
  if [[ -f "${E6_RECEIPT}" ]]; then
    SELECTED_AGENT="$(json_get "${E6_RECEIPT}" SELECTED_AGENT)"
    [[ "${SELECTED_AGENT}" != "DEANCHOR" ]] && AGENT_ARMS+=("${SELECTED_AGENT}")
  else
    AGENT_ARMS+=("<SELECTED_AGENT, if not DEANCHOR>")
  fi
  if [[ -f "${E6_FREEZE_DIR}/formal_gate.json" ]]; then
    AO_BUDGET="$(json_get "${E6_FREEZE_DIR}/formal_gate.json" per_group_budget_usd.AO_ORIG)"
    ARMS_BUDGET="$(json_get "${E6_FREEZE_DIR}/formal_gate.json" agent_arms_budget_usd)"
  fi
  # Free groups first. B1 = the E3 replay script on the new recording's detection index (skips existing outputs).
  e6_step "Stage 2c: B1 on the formal recording (0 USD, K=1)" \
    "$PYTHON_BIN" -B scripts/evaluation/e3_f4_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
      --out "${E6_FORMAL_OUT}/b1" --cases "${E6_FORMAL_CASES[@]}" --arms B1
  # R-N (zero cost): same frozen detections, seed = first ACQUIRE of the B1 run above (nothing else crosses). Output dir must not exist.
  if [[ -d "${E6_FORMAL_OUT}/rn" ]]; then
    echo "==> [Stage 2c: R-N formal] exists, skipped: ${E6_FORMAL_OUT}/rn"
  else
    e6_step "Stage 2c: R-N on the formal recording (0 USD, RN_U + RN_N)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_rule_neutral.py --root "${E6_FORMAL_ROOT}" --b1-runs "${E6_FORMAL_OUT}/b1" \
        --cases "${E6_FORMAL_CASES[@]}" --cameras "${CAMERA_CATALOG}" --out "${E6_FORMAL_OUT}/rn"
  fi
  # Paid groups, K=3. AO_ORIG = the unchanged E5 A-open (e5_run.py, skips existing outputs); budget = the gate's USD upper bound.
  if [[ "$DRY_RUN" != "1" && "$(count_files "${E6_FORMAL_OUT}/ao_orig" 'AO.k*.json')" -ge $(( ${#E6_FORMAL_CASES[@]} * 3 )) ]]; then
    echo "==> [Stage 2c: AO_ORIG] all 36 runs exist (resume), skipped"
  else
    e6_step "Stage 2c: AO_ORIG (K=3, paid, offline)" \
      "$PYTHON_BIN" -B scripts/evaluation/e5_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --out "${E6_FORMAL_OUT}/ao_orig" --usage-dir "${E6_FORMAL_OUT}/ledger-ao_orig" \
        --cases "${E6_FORMAL_CASES[@]}" --k 3 --mode offline --budget-usd "${AO_BUDGET}"
  fi
  e6_refresh_ledgers
  if e6_complete "${E6_FORMAL_OUT}/arms"; then
    echo "==> [Stage 2c: DEANCHOR/SELECTED] STATUS COMPLETE (resume), skipped"
  else
    e6_step "Stage 2c: ${AGENT_ARMS[*]} (K=3, paid)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --cases "${E6_FORMAL_CASES[@]}" --arms "${AGENT_ARMS[@]}" --k 3 --paid --max-usd "${ARMS_BUDGET}" \
        --baseline-json "${E6_RECON}" --receipt "${E6_RECEIPT}" --out "${E6_FORMAL_OUT}/arms" --extra-ledger "${E6_LEDGERS[@]}"
  fi
fi

if e6_phase_has verdict; then
  # 2d. Scoring and verdict (verdict_e6: prereg 3-4; GT is read here, on the scoring side only). Interface: PR #746 e6_verdict_run.py.
  if [[ "$DRY_RUN" != "1" && -f "${E6_FORMAL_OUT}/verdict/verdict_e6.json" ]]; then
    echo "==> [Stage 2d: verdict] exists (resume), skipped"
  else
    e6_step "Stage 2d: verdict_e6 scoring (0 USD)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_verdict_run.py --frozen-spec "${E6_FROZEN_SPEC}" --gt-root "${E6_RECORD_ROOT}" \
        --runs "${E6_FORMAL_OUT}/b1" "${E6_FORMAL_OUT}/ao_orig" "${E6_FORMAL_OUT}/arms" \
        --receipt "${E6_RECEIPT}" --out "${E6_FORMAL_OUT}/verdict"
  fi
fi

if e6_phase_has ablation; then
  # 2e. Exploratory ablations of the frozen SELECTED_AGENT (prereg S6, D403): NO_IMAGE, then NO_SPATIAL; never part of the Holm family.
  # Before each: re-read the ledgers, dry-run the step, and run only if cumulative + upper bound <= 90, else BUDGET_SKIPPED and go on.
  # Soft steps: a failure is recorded in STATUS.json and the run continues (the verdict of 2d is already written).
  # UNKNOWN (G3, PR #746 follow-up): e6_arms_run.py --ablation <X> and e6_verdict_run.py --ablation-runs are not in the CLI yet; until they
  # are, these steps fail softly with the CLI's own message.
  SELECTED_AGENT="<SELECTED_AGENT>"
  [[ -f "${E6_RECEIPT}" ]] && SELECTED_AGENT="$(json_get "${E6_RECEIPT}" SELECTED_AGENT)"
  mkdir -p "${E6_FORMAL_OUT}/ablation-status" 2>/dev/null || true
  for ABL in NO_IMAGE NO_SPATIAL; do
    ABL_OUT="${E6_FORMAL_OUT}/ablation-${ABL}"
    ABL_MARK="${E6_FORMAL_OUT}/ablation-status/${ABL}.json"
    if [[ "$DRY_RUN" != "1" && ( -f "${ABL_MARK}" ) ]]; then
      echo "==> [Stage 2e: ${ABL}] already decided ($(json_get "${ABL_MARK}" state)), skipped"; continue
    fi
    if e6_complete "${ABL_OUT}"; then
      echo "==> [Stage 2e: ${ABL}] STATUS COMPLETE (resume), skipped"; continue
    fi
    e6_refresh_ledgers
    e6_soft_step_to_file "Stage 2e: ${ABL} dry-run estimate" "${E6_FORMAL_OUT}/ablation-status/${ABL}.estimate.json" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --cases "${E6_FORMAL_CASES[@]}" --arms "${SELECTED_AGENT}" --k 3 --ablation "${ABL}" --dry-run || continue
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "    [DRY-RUN] budget-check (re-read ledgers; skip with BUDGET_SKIPPED if cumulative + estimate > ${CAP_USD}), then:"
      echo "    [DRY-RUN] e6_arms_run.py --paid --k 3 --cases E6-S01..S12 --arms ${SELECTED_AGENT} --ablation ${ABL} --max-usd <estimate> --out ${ABL_OUT} --extra-ledger ..."
      continue
    fi
    set +e
    "$PYTHON_BIN" -B scripts/evaluation/e6_select_arm.py budget-check --estimate "${E6_FORMAL_OUT}/ablation-status/${ABL}.estimate.json" \
      --base "${BASE_SPEND_USD}" --cap "${CAP_USD}" --out "${E6_FORMAL_OUT}/ablation-status/${ABL}.budget.json" --ledger "${E6_LEDGERS[@]}"
    rc=$?
    set -e
    if [[ $rc -eq 7 ]]; then
      printf '{"state": "BUDGET_SKIPPED"}\n' > "${ABL_MARK}"
      e6_status BUDGET_SKIPPED "Stage 2e: ${ABL}" "cumulative + dry-run upper bound > ${CAP_USD}"
      continue
    elif [[ $rc -ne 0 ]]; then
      e6_status SOFT_FAILED "Stage 2e: ${ABL} budget check" "exit ${rc}"
      continue
    fi
    e6_soft_step "Stage 2e: ${ABL} (K=3, paid, exploratory)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_arms_run.py --root "${E6_FORMAL_ROOT}" --cameras "${CAMERA_CATALOG}" \
        --cases "${E6_FORMAL_CASES[@]}" --arms "${SELECTED_AGENT}" --k 3 --ablation "${ABL}" --paid \
        --max-usd "$(json_get "${E6_FORMAL_OUT}/ablation-status/${ABL}.budget.json" max_usd)" --baseline-json "${E6_RECON}" \
        --receipt "${E6_RECEIPT}" --out "${ABL_OUT}" --extra-ledger "${E6_LEDGERS[@]}"
  done
  # Exploratory comparison (not in Holm): the same scorer on the ablation outputs that completed.
  ABL_RUNS=()
  for ABL in NO_IMAGE NO_SPATIAL; do e6_complete "${E6_FORMAL_OUT}/ablation-${ABL}" && ABL_RUNS+=("${E6_FORMAL_OUT}/ablation-${ABL}"); done
  if [[ "$DRY_RUN" == "1" || ${#ABL_RUNS[@]} -gt 0 ]]; then
    e6_soft_step "Stage 2e: exploratory comparison (verdict_e6, ablation runs)" \
      "$PYTHON_BIN" -B scripts/evaluation/e6_verdict_run.py --frozen-spec "${E6_FROZEN_SPEC}" --gt-root "${E6_RECORD_ROOT}" \
        --runs "${E6_FORMAL_OUT}/b1" "${E6_FORMAL_OUT}/ao_orig" "${E6_FORMAL_OUT}/arms" --receipt "${E6_RECEIPT}" \
        --ablation-runs ${ABL_RUNS[@]+"${ABL_RUNS[@]}"} --out "${E6_FORMAL_OUT}/verdict-exploratory"
  fi
  e6_status COMPLETE "Stage 2 (E6)" "all E6 phases finished"
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
