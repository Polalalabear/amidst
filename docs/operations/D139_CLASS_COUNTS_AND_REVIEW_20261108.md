# D139 counts 與 #493 獨立真實資料審查（2026-11-08）

父版固定為 `claude/ui-d139@46835218c600d99b8c973e52f62e8dd95e79ff15`。獨立一般 checkout：`~/amidst-d139-20261108`（不是 worktree）；preview 是 **8787 / PID 27641 / 啟動 head 4683521**，資料根 `~/amidst-artifacts/demo-owned-v1`。8785 / PID 18763 與 `claude/ui-redesign-v1@4ea0ebb` 全程未變，不重啟、不推送、不切換其 checkout。開子分支 `codex/d139-class-counts`，只合進 `claude/ui-d139`，不合併 #493。

## Counts 契約與驗證

每個 run 的 `detected_class_counts` 只彙總已索引的 `detections[].class_label`，正數、count 遞減／同數 label 字典序，與同 run 原有 `detection_index_sha256` 綁定。原 `supported_classes`、index、參數及其 hash 一概不改。計數是 detection 筆數，並不是人數／物件真實存在確認；不依目前 query 門檻篩選，也不重新推論。未知類別 fail closed。規格見 `docs/contracts/Q_DEMO_API_BOOTSTRAP_V1.md`，合成 fixture 明列 person=7、car=2。

```sh
AMIDST_DEMO_HOME="$HOME/amidst-artifacts/demo-owned-v1" AMIDST_REQUIRE_IMPL=1 PYTHONPATH=src \
 uv run --offline --no-project --python "$PWD/.venv/bin/python" python -B -m pytest -o addopts= -q \
 tests/q1q5/test_bootstrap_class_counts.py tests/q1q5/test_api.py \
 tests/q1q5/test_core_search_track_t.py tests/q1q5/test_scene_graphs.py
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
```

實跑 **pytest 170 passed / 26.05 s；Node 511 pass / 0 fail / 0 skip**。新 counts pytest 內含 B-05、A4-1、B4-1 三個真實索引的加總／類別／排序／pins 核對，另外檢查 null／empty、同數排序、非法 label、負向敏感欄位存取。未提供 owned package 的其他機器只跳過三個明確需要資料的整合測試，純合成契約測試仍可執行；本機本次沒有跳過。

## #493 逐項審查（指定 head，不把 counts 當成前台修正）

1. **要修**：`frontend/workbench-v2/ui-model.mjs:108–113` 把 recording 起訖當 `t0`／`t0+duration`。後端 `ClockMapping` 的有效 source 範圍是 `[0,duration]`，`wall_origin` 對應 source `t0`。合法 `t0=2s, duration=50s, origin=14:00:00` 的完整窗是 13:59:58～14:00:48；目前 UI 送 14:00:00～14:00:50，少前 2 秒且超尾 2 秒。後端明確只接受 rate=1；前台 rate=2 的測試不是已支援此契約的證據。三個 demo 目前 t0=0／rate=1，所以實資料空白時間仍正確對應整段窗。
2. **要修**：`frontend/workbench-v2/ui-shell.mjs:516` 只在 `plan.blindVisible` 時計算／渲染重現終點。真實整段窗的 estimate.as_of 是 A4=50s、B4=42s；重現時播放頭 A4=10.21s、B4=2.21s，`FUTURE_AS_OF` 正確拒絕未來 snapshot，結果曲線=0、終點=0。兩種高度都重現。步驟：選 A4 或 B4 → 追蹤 person → 起訖皆空 → 送出 → 拖到 W1 重現（A4 10.21s／B4 2.21s），應有的「已由 W1…觀測到／兩端已觀測，中段為推測」沒有出現。不要移除 FUTURE_AS_OF 守門；需由 #493 保留合法歷史 blind snapshot，或將已觀測終點與推測曲線可見性分開處理。
3. **展示資料／狀態通過；架構守門要修**：新增 presentation code 僅使用既有 response／display model，沒有新 GT／depth／visibility 讀取；白話仍分已觀測／推測／缺畫面／跟丟，身分未確認保留。但 no-allow architecture guard 在父版就 FAIL：`frontend/workbench-v2/ui-d139.test.mjs:88` 的負向 regex 帶禁止字串。應把此負向測試放到 `tests/` 範圍並保留執行，不用拼字拆分或 allow 掩蓋。counts 分支沒有改這個前台檔。
4. **調整期望後通過主流程；第 2 項仍要修**：原始 real-e2e 在兩高度都於 A4 blind 舊期望失敗（各 80 checks / 13 PNG）。允許的測試修正：空白時間驗證實際 WALL wall_range／整段 source 範圍，較早播放頭不得顯示未來曲線；B-05 深連結的正確提示是「尚無鏡頭位置資料」，不是無法預測；模式切換用 `#ui-modes`。修正後首次全流程兩高度各 **170 checks / 34 PNG / exit 0 / 0 page errors / 0 failed API**。另獨立 `blindReview` 明列第 2 項 NEEDS_FIX，沒有把它改成通過斷言。其後擴充 0.5× 實際下拉選擇的最終數字，見 PR／#445 最終回條與 LOCAL manifest。

## 8787 重現與證據

```sh
AMIDST_DEMO_HOME="$HOME/amidst-artifacts/demo-owned-v1" ./start_445_demo.command --port 8787
# 高度各用獨立 output；不要連 8785。
CORE_BASE_URL=http://127.0.0.1:8787 UI_QA_HEIGHT=900 UI_QA_OUTPUT=<LOCAL>/real-900 \
 node tests/browser/ui-redesign/real-e2e.mjs
```

LOCAL 根：`$AMIDST_ARTIFACTS/demo-owned-v1/evidence/d139-493/`。保留原版失敗、期望修正過程與完整兩高度結果；preview receipt 記 PID／啟動 SHA。每張圖 SHA／回應在各 browser-results；最終 manifest／counts JSON／logs 的 bytes 和 SHA 見 GitHub 回條。前台 runtime 仍是 4683521，E2E driver 是 counts 子分支的修改；最終交接必須區分兩者，不能宣稱畫面問題已修。code/config/contract/report 進 repo，RGB、venv、模型、screenshots 不進 Git。

子 PR 只交付 counts 與使用者允許的 real-e2e 修正；父 PR #493 的上述前台修正由 Claude 接手。D138 本機整理留到驗收 A 後；本次不刪原件或分支。


## 最終實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: runtime／E2E driver `c30ff9a9cda85427eab11b8489a4cfc7dcc970fa`，base #493 `46835218`；最終 head 與子 PR 連結見 GitHub 回條。只合入 `claude/ui-d139`，不合併 #493。
- Files changed: QAPI bootstrap、合成 bootstrap fixture、counts 契約／pytest、real-e2e 期望與審查 diagnostics、docs 索引與本交接／composition。沒有改 #493 前台實作。
- Commands run and results: 上列聚焦 pytest **170 PASS／0 skip**、Node **511 PASS／0 fail／0 skip**。exact `c30ff9a9` driver 在 8787 跑兩高度 real-e2e **各 176 checks／34 PNG／exit 0／0 page errors／0 failed API**，包含 0.5／1／1.5／2 下拉；synthetic **各 78 checks／exit 0**，DOM **25 checks**。`git diff --check` PASS。no-allow architecture：authority／schemas PASS，inference 仍為上述父版 `ui-d139.test.mjs:88` 的單一 FAIL，沒有新增 finding／allow／豁免。
- Artifacts: LOCAL `demo-owned-v1/evidence/d139-493/D139_RESULTS_MANIFEST.json`；精簡採證 payload **130 files／19,622,477 bytes**，SHA-256 **`abbe5db832f2130a63dbf168d43e32acc8d9cae763868c92895a771f5fb017b8`**，每份 payload 都列 bytes／hash。原始失敗／中間期望修正產物仍保留，不冒稱最終通過。完整 source composition 在同名 `D139_CLASS_COUNTS_COMPOSITION_20261108.json`。
- Verified: 三個實資料 run 的每筆 detection 計數加總、合法類別、排序和原 pins；B-05=1396／11 類、A4=1160／24 類、B4=2158／17 類，另 r005=33／10 類。這些是索引偵測數，包含模型誤判，不作物件真實存在聲明。兩高度所有主流程與不確定性，並且明確目視／記錄 W1 重現後終點缺失。沒有新推論、render、GT 或原件改寫。
- Not verified: 沒有重跑整套 Python suite或做量測 B；本次是指定聚焦測試和 Mac Chrome 8787 preview，B 依使用者安排待合併後才量。沒有宣稱 #493 全部通過。
- Deviations and handoff: #493 項目 1／2／守門列要修，由 Claude 接手前台；counts 自己的測試全過。8785 PID 18763 及其 4ea0ebb checkout 保持不動；獨立 8787 保留 4683521 原審查版供查看。D138 整理留到驗收 A 後，原件／分支不刪。
