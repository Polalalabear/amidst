# 同源 baseline 條線：一次工程驗收

2026-10-24，Refs #192/#202/#204/#206。可在人審期間進行的程式接線已交付；
正式 baseline、身分、研究正確性與獨立符合性仍未完成。各段保持 Draft，不合併。

## 已驗證的條線

固定的兩張全新 SYNTHETIC RGB → 20 幀安全 RGB manifest → 官方 CPU/FP32
RT-DETR/HSV 索引 → 同一 registry/clock/graph/parameters → Qwen3 與 RULE_ONLY
查找／持續追查 → 凍結輸出／provider trace／journals → kernel replay → 共用
Workbench Application/session 下的現有 Q-line UI／已錄製畫面回讀。

兩張圖由內建 imagegen 產生，只有工程控制用途；固定相同服裝條件不代表同一人。
來源 prompt 記錄在 LOCAL inputs/assets/GENERATION.md，不交給索引或模型。
runtime 只讀安全 RGB pixels、實際 detections 及獨立靜態工程拓樸；沒有 GT、actor
或 renderer 路線。SYNTHETIC 的 APPROVED 標記不能升成正式核定。

## 實際結果

| 項目 | 本次固定證據 |
|---|---|
| 真 detector | 20 forward / 20 完成，7 筆 person、red STRONG |
| CPU forward | 6221.13025 ms / 20 幀 = 3.214849906 fps |
| 其他階段 | model load 2581.474542 ms；完整 index build 6847.115875 ms；read/hash/decode/pre/post/HSV/encode/write 各自記錄 |
| baseline 樣本 | 查找／追查 × 兩 profile × 首次與兩次重複，共 12 COMPLETE |
| replay | 24 stage replay 一致，執行模型／外部網路呼叫 0 |
| 真 Qwen | Q3 6/6 timeout；Q5 3/3 timeout；兩者 LLM 採用 0；規則接手 |
| 追查輸出 | 每個追查樣本切 A→B 一次；沒有把工程事件分類當人工正確性 |
| 取樣 RSS | detector worker 789102592 bytes；Ollama service 各階段取樣峰值分列，最高 28311552 bytes；不同程序峰值不相加 |
| 未量欄位 | Qwen runner 未取得可靠枚舉、實體 VRAM peak、display fps、accuracy 保持 null；原 vm_stat/swap/ps 另存 |
| focused | A 63 PASS；B 113 PASS，另 3 項同源回歸；C 57 PASS；這些測試重疊，不相加 |
| 前端／HTTP | 5 個指定 Node 檔 59 PASS；同源 RGB hash、錄製跨 session 回讀、拒絕與語意澄清共 13 HTTP 檢查 PASS |
| 原版符合性 | #127 @994d34c 的 81 檔 bytes 未改；8 份 FIRST_CALL 兩 stage 全套，604 PASS／27 FAIL／11 SKIPPED_NO_CONTEXT，overall FAIL |
| 正式前檢 | 47 項 metadata／來源／磁碟檢查，BLOCKED/exit2，沒有正式 RGB/index 產製 |
| 原 Q3 回收 | 空白八題實際 importer：BLOCKED/exit2，8 pending，未產 public/expected，formal_rows=0 |

forward fps 只包含 forward；共享索引只建一次，不能把 20 次偵測重複記入每筆查詢。
各樣本透過同一 index content hash 連回 detector receipt；模板中未在該程序執行的
detector/model-load 欄位保留 null。巢狀計時不可加總。FIRST_CALL 不保證冷模型，
WARM_REPEAT 不保證模型已常駐，背景負載未控制。client timeout 不證明 server
立刻停止；沒有自動 preload/unload/restart/download，也沒有調寬原 2000/5000 ms 預算。

最終定量分母只含 LOCAL run/ 的 12 樣本與 9 次 Qwen 呼叫。前兩輪配置診斷另存
history/，不併入本輪成功分母。瀏覽器另測過 Qwen 解析及 Agent 各一個 request
sequence，畫面證實 timeout／RULE_FALLBACK；這兩次 UI 額外檢查只有截圖／狀態證據，
未回收完整 raw provider audit，不進定量報表。正式最小八題沒有被測模型執行。

## 一次驗收與重現

LOCAL 持久包 `q1q5-linked-baseline-v1_20261024/` 根 README 是唯一操作入口，包含
完整命令、固定 inputs、源碼、manifest、測試證據與截圖。`run-baseline.command`
用新的輸出目錄執行 `scripts/accept_q1q5_linked_baseline.py`；可加 --serve 接前景
工作台。`open-workbench.command` 只開既有固定錄製，不做模型推論；新的 private
目錄防止覆寫既有錄製。Ctrl-C 只停本次前景 server，Ollama 保留。

重現需要既有 Python/模型/官方來源與離線套件；清單在
configs/q1q5/linked_baseline_environment.json。pyproject.toml/uv.lock 仍是專案依賴
authority，額外既有 Pillow/torch/torchvision/PyYAML 與確切版本另列。不自動安裝。
既有 RT-DETR 來源目前在 LOCAL 外部目錄，遺失時須按固定官方 commit/hashes
重新準備；模型權重不封裝到 GitHub。

`linked_baseline_v1_sources.json` 固定 524 個 code 檔，可由原 source exporter 從
Git objects 重建；自己、此文件與最終收據不在清單中，避免自我引用，另由本 PR
及 LOCAL delivery manifest 固定。最終 source 包還含這三個交付 metadata 檔。
定量 run 使用的 composition 為 `180a048f25b654ea337dbdd00211edd668535b24408ce7c4adb9bbf87300ba23`，
保存在 RUNTIME_COMPOSITION.json；其後只補工作台重啟錄製與 QuietHandler，沒有
改 detector/query/provider/prompt/預算，不重跑同一組模型。最終完整 source composition
為 `6ed7dc707fb3ca120c6ca70b6d21bda856d682700ed3b02964c51ed2f14eafed`，
逐檔核對通過，輸出記錄與最新 UI pins 分開保存。

瀏覽器工程驗證：查找兩鏡、Q1 明選 A 起點、多鏡／單畫面、0.4 秒 TEMP_LOST、
0.8 秒 SEARCHING、1.0 秒 B 觀測、Qwen timeout／RULE_FALLBACK、固定錄製回讀及
重啟後回讀。RGB DOM 為 960×540、complete=true；這不是量測 display fps。
本包沿用 Q-line 子介面；legacy 主工作台導覽／完整產品整合與 Claude 獨立驗收
沒有在此宣稱完成，UI owner 及既有正式門檻維持原分工。

## 人審與正式啟用

Q3 importer 的輸入、版本、schema/clock 驗證與獨立評分入口見
Q1Q5_REVIEWED_INPUTS.md。只有 id/text 能進推論；expected/category/notes 留評估端。
正式 CLI 必須是另版 FROZEN protocol、顯式 permit、十三個 scope-bound receipts
及完整 protocol/cases/composition/registry/runtime pins。JSON 收據只驗 bytes/scope，
不能認證簽名者，也不解除 #145。

請一次核對程式／輸出與仍待人工的項目：yyyin 填好的 CSV、問題／不確定／未完成
清單及完整 folder/ZIP；Claude 獨立圖/ROI與符合性檢查；必要 HSV；八題獨立選擇及
精確 expected；run/camera/time/clock/圖/參數凍結；既有產品契約決策。原包保持原版。
核定與程式前置通過後，才依既有授權產正式 A4/B4 RGB → 正式索引 → baseline →
凍結輸出 → 獨立人工評分。其他 LLM/YOLO-World/ReID 比較留後續，每次只換一個因素。

Claude 的 LOCAL `claude-conformance-handoff.zip` 含八份完整錄製、未改的原 kit、
逐項報告與 source pins。#127/#135/#189 原證據不回改，不用 --only 隱藏 FAIL。
checkout/HEAD/真 index/468 個既有 dirty/untracked 檔與兩個舊包 manifest 均已核對保留。
