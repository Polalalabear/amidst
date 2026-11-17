# CX-L1 啟動與評估交接（#552）

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

精簡驗收收據列出 `$AMIDST_ARTIFACTS/cx552-20261117/` 各子項的檔數、大小、SHA及可重建性。執行期間輸出位於獨立clone的`local/evidence`，沒有在pin住的checkout寫檔。成果尚待Claude審查；合併由使用者執行。
