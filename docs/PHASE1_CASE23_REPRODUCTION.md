# Phase 1 Case 1–3 joint reproduction / 聯合驗收重建

日期：2026-10-14。**狀態：本次 primary、reproduction、clean-checkout delivery 與完整 repository validation 的結果待實際 receipts 補入。**
本文件提供已實作入口的執行方式，不把歷史 office、source-v1 probe 或 unit tests 的結果當成本次 formal PASS。
驗收範圍與限定依 [Case2／Case3 acceptance](PHASE1_CASE23_ACCEPTANCE.md)。

## 執行位置與固定輸入

本次工作樹是 `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-formal`，
branch 為 `codex/phase1-case23-formal`，研究起點為 `883204af854bed301506b39d63ccb33312b79ff2`。
最終 reproduction 必須另記**實際** clean-checkout commit；此起點 SHA 不能代替包含新 producer 的最終 SHA。

| 輸入／輸出 | 本次位置或固定值 |
| --- | --- |
| Source scene | `/Users/polalabear/Developer/amidst/blender/school_v3.blend` |
| Source SHA-256 | `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| Source size | 468,300,506 bytes |
| Source schedule config | `configs/finalization/scoped_case23_export_v2.json` |
| Master definition | `configs/finalization/case123_formal_experiment_v2.json`；由 primary 新建 |
| Planned primary release | `data/finalization/reviewed_run_case123_formal_v2_20261014` |
| Runtime | CPython **3.12.12**、committed `pyproject.toml` 與 `uv.lock` |
| Native Blender | `/Applications/Blender.app/Contents/MacOS/Blender`；版本／build 由實際 export manifest 保存 |
| Original scale / seeds / sampling | 0.0247 m/BU；export seed 20261005；inference seed 42；inclusive 5 Hz |

Master 在新 source simulation／inference 前固定 producer 的 transitive local imports、source config、
原核准輸入、metrics 與原 budget。輸出 definition 不參與自己的 hash。
Case1 使用新的 original-office child；Case2／Case3 使用已核准 exact 六-cell union 與獨立 Case2 addendum。
`case3_short_control`、`case3_long_stress` 各自保留實際可見 endpoints／recoveries。
兩個 child 的歷史 scope、`BLOCKED` 與 `N/A` 結果留在自己的報表，不改名為新 Case2／Case3。

## Locked offline 環境與 local hydration

從本次工作樹執行，先確認目錄與 branch。下列 cache 是此環境已建立的 local cache；
新機器須先提供相同 Python／locked dependencies，offline 命令不會自動下載缺少的依賴。

```sh
phase1_checkout=/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-formal
phase1_canonical=/Users/polalabear/Developer/amidst
phase1_source="$phase1_canonical/blender/school_v3.blend"
phase1_blender=/Applications/Blender.app/Contents/MacOS/Blender
phase1_source_config=configs/finalization/scoped_case23_export_v2.json
phase1_master=configs/finalization/case123_formal_experiment_v2.json
phase1_run=data/finalization/reviewed_run_case123_formal_v2_20261014
cd "$phase1_checkout"
git branch --show-current
git status --short
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv sync --locked --offline --python 3.12.12
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python --version
```

Large source assets、原 review frames、raw physical gzip blobs 及新 dataset／GT／recipe／RRD 留在本機。
乾淨 checkout 仍需 hydration，不能僅 clone 小型 summaries 就宣稱完成 numerical verification。
原四份 `source_evidence.json.gz`、`geometry.json.gz`、`floor_support_details.json.gz`、
`obstacle_collider_details.json.gz` 須符合 committed artifact manifest。
既有 exact bytes 的恢復方式見 [persistent runtime](PHASE1_RESTORED_RUNTIME.md#恢復原-inputs--restore-original-inputs)
與 [materialization guide](PHYSICAL_EVIDENCE_MATERIALIZATION.md#明確重建流程)。

本次工作樹已提供恢復用 inputs；新 checkout 先從持久、已驗 hash 的 hydration root 補齊 missing bytes，
再驗原 review package／locks。matching existing bytes 保留；mismatch 停止，不以新 formal dataset 取代原 review inputs。
以下使用原持久 finalization 工作樹作 historical hydration root：

```sh
phase1_hydration_root="$phase1_canonical/.local-worktrees/phase1-finalization"
phase1_physical_bundle=data/scene_audit/phase1_physical_policy_approval_20261006
for phase1_blob in source_evidence.json.gz geometry.json.gz floor_support_details.json.gz obstacle_collider_details.json.gz
do
  cp -n "$phase1_hydration_root/$phase1_physical_bundle/$phase1_blob" "$phase1_physical_bundle/$phase1_blob"
done
mkdir -p blender data/cameras
for phase1_scene in school_v2.blend school_v3.blend
do
  if [ ! -e "blender/$phase1_scene" ] && [ ! -L "blender/$phase1_scene" ]; then
    ln -s "$phase1_canonical/blender/$phase1_scene" "blender/$phase1_scene"
  fi
done
cp -n "$phase1_canonical/data/cameras/school_v2_calibration_v1.json" data/cameras/
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python -m amidst.reviewed_input_hydration \
  --root "$phase1_checkout" --historical-root "$phase1_hydration_root" \
  --durable-review "$phase1_canonical/data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review"
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python -m amidst.materialize_physical_evidence \
  --source-scene "$phase1_source" --verify-only
```

Raw physical blobs 缺失時可依 materialization guide，以原 Blender／source／config 重建並核對原 pins。
這是恢復原證據，不是重新核准語意或調整本次資料。原 `.blend` 不儲存、不改 scale、不複製成 bulk archive。

本機 macOS Blender 啟動路徑需要可初始化 host Metal 的 runtime。此環境已觀察到 sandbox 的 Metal startup crash，
同一 Blender startup preflight 在 unsandbox host 可執行；這是執行環境差異，沒有由模型替代 source raycast 的 PASS。
正式命令必須真正完成 native exports；Blender startup 成功也不單獨解除 research gates。

## Primary：建立新 master 與同一聯合 release

只有當 master 與 primary output **尚不存在**時使用 `primary`。檔案已存在時保留原件，改用下節 `rerun` 與新 output。
不要把命令執行到既有 recorded run。

```sh
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python scripts/run_phase1_joint_case23.py primary \
  --source "$phase1_source" --blender "$phase1_blender" \
  --source-config "$phase1_source_config" --config "$phase1_master" --output "$phase1_run"
```

[Joint runner](../scripts/run_phase1_joint_case23.py) 的實際順序是：

1. Regenerate intact source numerical authority，建立新 frozen master 與 source export lock。
2. 執行 scoped 與 original-office 兩個 native Blender exports；原 office 使用原 producer／config／authority。
3. Original-office primary inference、scoped primary inference 分別完成並 freeze；不開 evaluation／simulation reference partitions。
4. 建立 `joint_inference_freeze.json`，當次核對**兩個** child 的 exact manifest、source、seeds、設定、原 approval 與 GT=false。
5. 才執行兩個 independent evaluations、metrics／charts／source-bound demos，組成 joint table 與 Case3 growth record。
6. 比對 source SHA／size／mtime 的 before／after，保存 `primary_run_receipt.json`。

主要 artifacts：

| 路徑（相對 release） | 用途 |
| --- | --- |
| `office/dataset`, `office/inference_primary`, `office/evaluation` | Fresh Case1 原 office evidence；其他 original child rows 也保留 |
| `scoped/dataset`, `scoped/inference_primary`, `scoped/evaluation` | Case2／Case3 與兩個 stress controls 的完整資料與結果 |
| `joint_inference_freeze.json` | 兩 child 全部 primary predictions 在任何 reference evaluation 前凍結 |
| `benchmark_table.json`, `.csv`, `.md` | Case1–3、stress、A/B/C 與 supported ablations；N/A、空候選與缺測量照實保留 |
| `case3_growth.json` | Main／short／long 的 counts、實際 frozen gap times 與 native endpoints；不宣稱 matched-anchor 因果 |
| `verification.json`, `primary_run_receipt.json` | 本次 joint completeness／尚缺 gates，及 source／master integrity |

Case2／Case3 primary demos 位於 `scoped/evaluation/demos/<case>/`，含 `scoped.rrd`、`preview.png`、
`presentation.json`。Exact union 孔洞與各 cell body guard 保留；source 3D footpoints 是 `PROJECTED`，
候選是 `INFERRED_GAP`；primary recording 的 GT=false，reader verification 為必要證據。
原 office Case1 demo 保留其 original adapter 與 authority；stress 不複製 primary demo。

## Rerun：重用 exact master，重新執行全部 primary stages

`rerun` 讀取並重新驗證原 master bytes，不建立新 definition。它仍重新執行 numerical authority、
兩次 native export、兩個 inference、joint freeze、evaluation 與報表；不是複製原輸出。
選擇尚不存在的 destination，例如：

```sh
phase1_rerun=data/finalization/reviewed_run_case123_formal_v2_rerun_20261014
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python scripts/run_phase1_joint_case23.py rerun \
  --source "$phase1_source" --blender "$phase1_blender" \
  --source-config "$phase1_source_config" --config "$phase1_master" --output "$phase1_rerun"
```

原 master 或 producer／protected inputs 改變時，exact-master rerun 必須拒絕。
新研究版本要另建 master／output，不能回寫已凍結實驗。

## Reproduce：repeat／fresh-process／order／poison／clean checkout

先提供真正獨立、初始 clean 的 checkout，包含最終 producer／master／source config，完成相同 locked environment
與 exact-input hydration。`expected_commit` 必須是該 checkout 的完整 40-hex 實際 commit；dirty tree 或不符 SHA 會拒絕。
Source 指向同一 immutable canonical `.blend`；CleanSpec 的 `output` 必須尚不存在。

以下是**待填入實際 clean checkout 與 commit**的 JSON 模板。存為 clean checkout **外**的本機 `phase1_clean_checkout_spec.json`，
避免新增非 ignored 檔案使 clean guard 拒絕。Root／source／executables／output 使用 absolute paths；兩個 `*_relative_path`
保持 checkout-relative。`joint_release` 必須設 `true` 才會重新執行及比較完整 office＋scoped delivery。

```json
{
  "root": "/absolute/path/to/clean-phase1-checkout",
  "expected_commit": "REPLACE_WITH_ACTUAL_40_HEX_COMMIT",
  "master_relative_path": "configs/finalization/case123_formal_experiment_v2.json",
  "source_config_relative_path": "configs/finalization/scoped_case23_export_v2.json",
  "source": "/Users/polalabear/Developer/amidst/blender/school_v3.blend",
  "python_executable": "/absolute/path/to/clean-phase1-checkout/.venv/bin/python",
  "blender_executable": "/Applications/Blender.app/Contents/MacOS/Blender",
  "output": "/absolute/path/to/clean-phase1-checkout/data/finalization/reviewed_run_case123_formal_v2_clean_20261014",
  "joint_release": true
}
```

`reproduce --output` 指向**既有 primary release**，不是新的 primary destination。
Runner 在其下新建 `office/reproduction/`、`reproduction/` 與 `reproduction_receipt.json`；這些 reproduction outputs 也不得覆寫。
Source／Blender／source-config flags 仍為 CLI 必填，使用 primary 的同一值；clean rerun 的 paths 由 typed CleanSpec 決定。

```sh
phase1_clean_spec=/absolute/path/to/phase1_clean_checkout_spec.json
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync python scripts/run_phase1_joint_case23.py reproduce \
  --source "$phase1_source" --blender "$phase1_blender" \
  --source-config "$phase1_source_config" --config "$phase1_master" --output "$phase1_run" \
  --clean-checkout-spec "$phase1_clean_spec"
```

Original-office reproduction 沿用原 repeat／fresh-process／order／GT-recipe-annotation poison。
Scoped runner 在同一 process 載入 intact provider 一次供 repeat／order／poison 使用；fresh-process 仍真正啟動新 Python inference。
Clean-checkout joint mode 真正執行 `rerun` 的兩 native exports 與全套 primary workflow，再比較兩 child 與 joint delivery。
沒有 clean-checkout full delivery 時，scoped reproduction 保持 `INCOMPLETE`。

Order check 反轉已 projected samples 的 computational order，再做 canonical aggregation；原 observations／context bytes 與 source hashes 不重寫。
Poison 在原 primary freeze 成立後，複製 allowlisted artifact bytes，改 evaluation GT、simulation recipe、reference annotations；
inference-only payloads 與 manifest bytes 保持原值。Metrics sensitivity 只測已有 timed C candidates 的 gap population；
`N/A_NO_TIMED_CANDIDATES` 保留，invalid poisoned annotations 不代表跑過完整 poisoned-annotation evaluation。

完整 comparison 要求 manifest、canonical inference、candidate order／termination／counts，以及 JSON／CSV／Markdown population 相符。
必要非 runtime 圖表、Case2／Case3 RRD／PNG／presentation、reader receipt 都須存在。
僅明列的 numeric runtime、root paths、RRD container metadata／hash 與 runtime-plot pixels 作非 canonical 排除；
仍核各 artifact 的實際 hash、count、reader status 與 presentation 的 source geometry／provenance。
缺資料、未知或失敗須留在 receipt，不能填假 0／PASS。

## 完整 validation、結果與保留分類

Reproduction 與完整 repository validation 是分開的 gates。以下列出執行命令，**未聲稱本次已完成**：

```sh
BLENDER_BIN="$phase1_blender" AMIDST_PHYSICAL_SOURCE_SCENE="$phase1_source" \
  UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync pytest --require-physical-evidence -rs
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync ruff check .
UV_CACHE_DIR=/private/tmp/amidst-case23-uv-cache uv run --offline --no-sync mypy
git diff --check
```

本次結果由主線執行後補：exact master SHA、兩 dataset manifests、兩 child freezes、joint freeze、primary／reproduction receipts、
clean commit／delivery comparison、tests passed／failed／skipped、Ruff／mypy／source fingerprint。
`formal_case_execution_complete` 不是 full Exit／freeze；reproduction 與 repository validation 尚未核對時保留 PENDING、
`freeze_allowed=false`。各 Case 與 supported ablations 分開報告，overall Coverage@3 weighting 仍未核准。
Case4 保持 DEFERRED，school surface authority 未獲整校 certification；Phase2 不修改。

| 分類 | 保留範圍與時機 |
| --- | --- |
| `KEEP_UNTIL_SHARED_WORK_COMPLETE` | 此工作樹、primary／rerun／clean raw outputs、datasets、frozen inference、RRD／plots、numerical inputs、hydration inputs；共享工作與驗證完成前保留 |
| `KEEP_IMMUTABLE_SOURCE_AND_PINS` | Canonical source assets、original HR／protocol／approval／config bytes、master、concise manifests／receipts；不回寫、不刪除 |
| `REVIEW_AFTER_SHARED_COMPLETION` | 完成後重新查 runtime owners、active consumers、dirty state、unique evidence 與可重建性；本表不授權刪除 |

不自動將任何項目標為 `DeleteCandidate`，不刪他人工作樹、不停他人服務。
確認共享工作完成與新的清理授權後，才執行有證據的 cleanup；保留精簡 hashes／manifests／receipts，而不是另複製 `.blend` bulk archive。
