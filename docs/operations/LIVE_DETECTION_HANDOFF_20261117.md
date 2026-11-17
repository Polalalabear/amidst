# CX-L1 啟動與評估交接（#552）

**最新狀態（D273，2026-11-18）：近期紅衣候選鏡頭修正已實跑；固定RGB／新實跑品質與protocol條件PASS，ENTRY因baseline tracker無正確重鎖仍UNKNOWN，整體NOT_PASSED。#559保持Draft，與新main另有待整合衝突。詳見 `docs/evaluation/LIVE_DETECTION_SCHEDULE_D273_20261118.md`。**

**修改C歷史狀態：已merge main並實跑，當時驗收NOT_PASSED。** 組成、逐條條件、新證據與重現命令見 `docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md`。以下修改A時的等待記錄屬歷史狀態。

以本 PR 的 `codex/feat-live-detection` 為單一程式來源，base `main@31a69177`。不需要其他未合併分支，不更新8785或demo-pin。評估報告：`docs/evaluation/LIVE_DETECTION_20261117.md`；精簡收據與檔案hash：`docs/evaluation/live_detection_20261117/`。

## 啟動

使用自己的 checkout、現有 uv Python 環境及唯讀的 LOCAL 素材；`SHARED_LOCAL`、`PYTHON`、`AMIDST_ARTIFACTS` 由執行者指定，不能指向新資產副本或把原始檔覆蓋。`AMIDST_ARTIFACTS` 是新證據的輸出根，不是素材根。Node依賴沿用 `frontend/live-mode/package-lock.json`。

```bash
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python -m amidst.live_mode.server --port 8797 --device mps --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --assets "$SHARED_LOCAL/data/live-assets-20261115" --cameras "$SHARED_LOCAL/data/r004-build-v2-20261021/safe_static/cameras.json" --advisor off
```

預設即為校準後的letterbox與一般0.15／ENTRY0.05。`/config`提供實際設定。基準對照另加 `--det-resize-mode stretch --min-score 0.35 --camera-min-score CAM_ENTRY=0.35`；只改一般門檻不會覆寫ENTRY的獨立校準值。新設定的門檻經固定格點選擇，換場景／角色／相機需重新量測；不是COCO或正式研究預設。

## 固定RGB評估

```bash
LIVE_BASE=http://127.0.0.1:8797 node scripts/live_mode/record_detection_bench.mjs "$AMIDST_ARTIFACTS/cx552-20261117/recording"
node scripts/live_mode/detection_manifest.mjs "$AMIDST_ARTIFACTS/cx552-20261117/recording" "$SHARED_LOCAL"
# 以下各variant串行執行，避免GPU競爭；原始RGB不變。
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python scripts/live_mode/detection_bench.py --recording "$AMIDST_ARTIFACTS/cx552-20261117/recording" --out "$AMIDST_ARTIFACTS/cx552-20261117/diagnosis" --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --variant deployed
# 另跑stretch；原因對照跑letterbox、bright、highres（三台對照可加--only-three）。
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python scripts/live_mode/detection_score.py --work "$AMIDST_ARTIFACTS/cx552-20261117"
```

`deployed.summary.json`的`calibrated_profile`才是交付設定；其他`thresholds`為一般門檻對照。保存所有低至0.05的偵測，維持舊sweep的最高IoU框評分；不以預先刪框或改成任一框命中提高指標。GT只在錄製及推論後計分，推論工具只讀RGB。

## 追蹤與延遲

```bash
AMIDST_ROOT="$SHARED_ROOT" PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python scripts/live_mode/replay_bench.py --work "$AMIDST_ARTIFACTS/cx552-20261117/replay" --src "sol2=$SHARED_LOCAL/evidence/live-mode-advisor-20261116/sol2" --src "gate=$SHARED_LOCAL/evidence/live-mode-tracker-20261116/gate" --config 'gate4_off=--mode off --gate-m 4'
# 在frontend/live-mode執行，每組50秒，基準/交付各兩次；同一硬體但非獨占。
LIVE_BASE=http://127.0.0.1:8797 OUT="$AMIDST_ARTIFACTS/cx552-20261117/latency" node measure/latency.mjs candidate_r1 'auto=B4&duration=42&model=glb&w=320&h=180&fps=2&cams=CAM_W1,CAM_W2,CAM_R101_IN' 50
```

`SHARED_ROOT`僅讓既有重播找到唯讀safe_static相機目錄；輸出仍明確指向`AMIDST_ARTIFACTS`。重播不讀API key、不跑模型裁決。原38段只有舊偵測，另外使用`record_detection_route.mjs`保存同批RGB封包，再用`redetect_route.py`重跑並經相同gate4_off評分。命令格式見這兩個檔案頂部／`--help`。A4/B4各一段的配對重播只作工程對照，不當統計。

## LOCAL證據保存

原始RGB、HTTP影像封包、逐框偵測與逐tick結果全部LOCAL；不複製原始GLB、權重、影片或GT資產。固定錄製`recording/MANIFEST.json`列2,057個檔案、16,486,517 bytes及來源SHA，含1,432張320×180（8張空場景）、624張640×360和一份評分標籤；manifest本身另計。來源GLB／相機／模型的SHA都在manifest，重錄需重新計hash，不能承諾相同延遲。

$AMIDST_ARTIFACTS 預設應指向共用 `local/evidence`；D259已把cx552及cx555實體歸位，核對原manifest一致。

精簡驗收收據列出 `$AMIDST_ARTIFACTS/cx552-20261117/` 各子項的檔數、大小、SHA及可重建性。執行期間輸出位於獨立clone的`local/evidence`，沒有在pin住的checkout寫檔。成果尚待Claude審查；合併由使用者執行。


## D261 歸因重現與整合關卡

修改A已通過±0.02規則，保留ENTRY0.05。反事實0.15命中率126/236（53.39%）、0.05為173/236（73.31%）；單ENTRY誤檢/影格0.15為0、0.05為0.38559。精確配對及取捨見評估報告與 `entry_threshold_attribution.json`。

**以下及所有啟動器命令請在自己的 clone 執行**，不要在pin住的checkout執行；`.local/demo-cache/uv` 會寫入執行clone。新輸出用獨立證據根，不覆寫原有frozen inputs。下列 `ORIGINAL` 指向已歸位的舊資料，`ATTR` 指向本次新輸出。

```bash
ORIGINAL="$SHARED_LOCAL/evidence/cx552-20261117"
ATTR="$AMIDST_ARTIFACTS/cx552-d261-20261117"
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/redetect_route.py --recording "$ORIGINAL/routes" --out "$ATTR/entry015" --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --min-score 0.15 --camera-min-score CAM_ENTRY=0.15
AMIDST_ROOT="$SHARED_ROOT" PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/replay_bench.py --work "$ATTR/paired_replay" --src "entry005=$ORIGINAL/routes/redetected" --src "entry015=$ATTR/entry015" --config 'gate4_off=--mode off --gate-m 4'
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/entry_threshold_receipt.py --original "$ORIGINAL" --work "$ATTR" --out docs/evaluation/live_detection_20261117/entry_threshold_attribution.json
```

GT只在推論完成後評分。`entry_threshold_receipt.py` 重算原格點指標、精確驗證門檻以外輸出不變、套用指定規則，並產生input inventory和新manifest。原格點偵測沿用已保存RGB推論，沒有新錄製。完整新LOCAL清單18檔1,039,599 bytes，manifest SHA在評估報告；時間及浮點結果不保證逐bytes重建。

#560／#561已轉Ready但尚待使用者合併。**修改C是#559的合併前關卡**：僅在#561合入main後，merge main到此分支（merge commit、不得rebase/force-push），保留/config兩邊鍵及逐cam門檻，再用本偵測器新輸出跑聯合驗證。不以修改A或歷史全套gate代替聯合驗證；目前未部署8785。
