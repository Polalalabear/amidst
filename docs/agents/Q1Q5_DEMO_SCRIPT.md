# Q1–Q5 Demo 操作腳本（草稿，交 Claude 週日改寫）

狀態：**工程稿；正式 r004 Demo NOT_READY；沒有人工驗收或準確率結論。**

依據：[#93 D70／衝刺計畫](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6307794669)、[D71](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6308081801)、[#90 設計／D66](https://github.com/Polalalabear/amidst/pull/90)、[#144 契約提案](https://github.com/Polalalabear/amidst/issues/144)。Codex 寫操作框架及程式紀錄；Claude 改寫旁白、審 staging 並獨立做瀏覽器驗收。組員提供題目、答案、RGB 標註與人工判定；本文件不提供標準答案。

## 1. 已能重現的工程試用

這一段只驗程式接線。它使用實際 Q kernels、現有 Application、SYNTHETIC bindings 與明示的 Workbench session test double；不讀原始影片、GT 或人物路線，不連 Ollama，不含 RGB。空畫面須顯示 MISSING，不能用它宣稱辨識或真實畫面驗收。

LOCAL 工程包：

```text
~/amidst-artifacts/q1q5-staging-20261021/engineering-qa-v3/
```

`COMPOSITION.json` 逐檔列 SHA-256、staging 基底與組合的 Draft PR heads；其 bytes SHA-256：

```text
cdb5fc9233347fbf20392750c73eac26a3b861e2ab45ddb9adeebdff06c94c0d
```

這是具名的多 PR source 組合，**不是單一 staging checkout**。v1 保留原接線證據；v2 的啟動檢查發現未建立錄製目錄而中止；v3 已補目錄建立並實際啟動，不覆寫前版。

啟動前確認 56148 沒有其他服務；若有人正在使用，停止本步，不終止對方程序。使用既有 Python 環境，不安裝套件或下載權重：

```sh
Q1Q5_QA_ROOT="$HOME/amidst-artifacts/q1q5-staging-20261021/engineering-qa-v3"
Q1Q5_PYTHON="/Users/polalabear/Developer/amidst-claude/.venv/bin/python"
lsof -nP -iTCP:56148 -sTCP:LISTEN
df -k "$Q1Q5_QA_ROOT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_QA_ROOT/snapshot/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_QA_ROOT/serve122.py"
```

這個指令已在本機以交付目錄執行；只在 loopback 啟動，Ctrl+C 停止自己啟動的服務。啟動時在自有目錄新增一份 append-only 合成錄製檔，產製前後記 df；低於 8 GiB 拒絕新增。沒有啟動 Blender、模型或正式資料產製。

網址：

- Demo：<http://127.0.0.1:56148/workbench-v2/>
- 審核：<http://127.0.0.1:56148/workbench-v2/?mode=review>
- 明示的 UI 錄製樣本：`?source=fixture`，審核再加 `&mode=review`。全部 SYNTHETIC，排除正式評估。

工程操作：

1. 確認來源條為 `LIVE · SYNTHETIC`、切換方式預設「規則」。
2. 開「條件表單」，保留來源提供的 person／未指定顏色與來源微秒範圍，執行；這是機械控制測試，不是一份人工題目。
3. 檢查相符／已推論但不符／未評估三區沒有合併；切 1／2／4／8 格與分頁，原 rank 不變。
4. 「開啟錄製回應」讀已 pin 的合成 session，來源條應改成 `RECORDED · SYNTHETIC`；切多鏡頭／單畫面，播放及步進。
5. 回「找相機」做新查詢，來源條恢復 LIVE。錄製清單不應關掉已註冊的 live query。
6. 審核網址才有「開始審核」與 Q4／Q5 內部紀錄。Demo 只呈現畫面與切換，不顯示內部判斷。

此工程包的 v3 HTTP 紀錄與 SOURCE 回應可核對離線 replay；它的 `SYNTHETIC` 不因 transport 寫 LIVE／RECORDED 就變成正式資料。

## 2. 正式 r004 啟動前要補齊的實際資料

以下目前不能填「已完成」：

| 項目 | 目前實際狀態 | 接續位置 |
| --- | --- | --- |
| A4／B4 RGB、獨立 run／clock、安全匯出與逐檔 pins | NONE；D70 已授權渲染範圍，但事件前圖／ROI 獨立檢查與凍結收據尚未成立 | #115、#117、D68 |
| r004 圖／每台出口區域 | 已有 8 台靜態 PROPOSED 圖，#163；不等於 G4 或物理通行核准 | #116、#117／G4 |
| HSV 正式核定 | #158 是提案，Q-19 的獨立檢查／使用者核定未完成；既有 §11 初值核定不替代新 HSV 提案核定 | #114／G6 |
| 正式偵測索引 | NONE；不把 preview index 或試用 smoke 當正式 A4／B4 索引 | #118 |
| 正式組員審查包 | A／B1 v0-pilot 已有；r004 v1 等 #115／#118 | #147 |
| 端點與 UI 的 staging 整合 | #174–#177、#180 為 Draft；上游 #154／#157／#169／#172 仍被原 kit 差異阻塞 | #145、#153／#156／#170／#178 |
| 正式 live Agent／Q3 LLM 接線 | Controller／provider 程式已測；正式 registry Agent 工廠與 §14-23 的 parse receipt 語意仍未定 | #111／#112、#144 |
| source build／ui.commit | 工程包有 composition pins，單一正式整合 commit 尚無；審核匯出目前 ui.commit 可為 UNKNOWN | Claude 整合後補實際 SHA |

D68 要圖／ROI 在事件渲染前凍結，契約 §14-4(a) 記有先獨立檢查；目前 #117 沒有完成收據。本稿不把 PROPOSED 檔案的 hash 自動當作獨立檢查或 G4 核准。D70 的 G5 渲染授權已存在，不重複要求授權。原始 r003／A／B1、#127 測試包與 #135 分支都保留。

正式資料備妥後，沿現有啟動器接線，registry 要有獨立可信 file SHA-256；不要臨時從同一份未知檔重算 hash 就當成可信 pin。下列是**待資料成立後的指令形狀，未在正式 r004 執行**：

```sh
# 這些值必須來自已審查的整合版本／資料收據；目前 UNKNOWN，不填造路徑。
# Q1Q5_UI_ROOT、Q1Q5_EVIDENCE_ROOT、Q1Q5_ASSETS_ROOT、Q1Q5_PRESETS_JSON
# Q1Q5_REGISTRY_JSON、Q1Q5_REGISTRY_EXPECTED_SHA256、Q1Q5_PYTHON
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_UI_ROOT/src" \
AMIDST_Q1Q5_REGISTRY="$Q1Q5_REGISTRY_JSON" \
AMIDST_Q1Q5_REGISTRY_SHA256="$Q1Q5_REGISTRY_EXPECTED_SHA256" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_UI_ROOT/scripts/office_demo_backend.py" serve \
  --ui-repo "$Q1Q5_UI_ROOT" --evidence-repo "$Q1Q5_EVIDENCE_ROOT" \
  --assets-repo "$Q1Q5_ASSETS_ROOT" --presets "$Q1Q5_PRESETS_JSON" --port 8765
```

啟動器參數已從程式核對。未配置 registry 必須 NOT_READY，不切換成 fixture，不隱式建資料或啟動模型。不要為示範重設目前有未提交檔的 checkout，也不要另建 worktree。

## 3. 正式 Demo 流程草稿（題目／預期由組員提供）

| 段落 | 操作 | 可說的旁白 | 必須保留的界線 |
| --- | --- | --- | --- |
| 來源 | 選固定 run，核對來源條、run／clock／索引／參數／圖 pins | 「這次展示使用這一份凍結來源。」 | 展示時鐘不是拍攝牆鐘；A4／B4 不跨 run 串人。 |
| Q1 | 用組員提供的有命中、零命中、支援類別與不支援條件案例查詢 | 「相符結果是取樣到的條件相符觀測；排序是建議檢視順序。」 | NO_MATCH 只說已推論影格沒找到；未評估、MISSING、OUT_OF_RANGE 分開。PARTIAL 不掩飾未涵蓋範圍。 |
| Q3 | 輸入組員提供的句子；展示 PARSED 與需要釐清／不支援／無法解析 | 「解析成功後直接執行；需要補充時先停下，不猜條件或時間。」 | 日期／時區取宣告 clock；規則／LLM 與 fallback audit 只在審核模式讀。不能把 client origin 當 LLM 使用證據。 |
| 起點 | 從代表觀測選起點；多筆時由人選，不自動挑 | 「這是選定觀測，身分尚未確認。」 | request、run、時間與 observation refs 綁定，不從 GT 指定人物。 |
| Q2／Q5 | 先 RULE_ONLY；播放多鏡頭，再單畫面事件播放 | 「系統背景檢查目前目標觀測；失聯後進入候選搜尋，支持成立才硬切。」 | UI 重播已算完 session，不在前端重算狀態機；來源時間只前進。GAP 不補位置或框。 |
| 失聯／return | 展示錄製結果中的暫失、切鏡與回原鏡頭 | 「這段沒有觀測支持；回原鏡頭仍是目前來源時間。」 | 不倒帶到最後看到的影格；沒有找到不等於人不在，條件相符不等於同一人。 |
| Agent／兜底 | 設定與 pins 核准後選 AGENT_SEQUENTIAL；另用受控故障錄製展示接手 | 「Agent 故障時，決定性規則接手整段 session；fallback_budget_ms 只記錄，不截斷。」 | 受控故障不是模型品質結果。已接受／拒絕、agent_attempted／used／fallback_used 依 journal 照實列。 |
| 審核 | 用 `?mode=review` 打開決策、Q4 evidence 與原始引用；人工逐項判定及匯出 | 「自動檢查是格式與一致性提示；人工判定由審核人負責。」 | mode 不擴權、不改請求；缺核准參數原文時 guard 核對 NOT_APPLICABLE。預期清單不上傳。 |
| replay | 載入可信 file pin 的錄製 response／journals／trace，保持原 hash | 「這段可以在不連 Ollama 時重播。」 | domain response replay 與完整 Agent trace replay 分開驗。真實 RGB 仍須已註冊的 safe run 與 #80 grant/pins，不能從 GT 重建。 |

旁白不填「正確答案是哪台、哪段、哪人」；也不把合成程式測試、畫面播放、幾何來源或 hash 一致當作辨識、身分、物理安全或正式研究驗收。

## 4. Claude 週日接手清單

1. 核對最新 staging head、每個 PR 的 head／A/B 等級；B 項逐一審，不更新 main，直到使用者既定流程允許。
2. 先處理獨立驗證 #145；#127／#135 只有 Claude 能改。實際 domain kit FAIL 的程式不合併。
3. 完成 #117 的獨立靜態圖／ROI 檢查與事件前凍結，再續 #115；新 HSV 依 Q-19 檢查／核定後續 #118。不看事件答案回調圖或 HSV。
4. 把工程 composition 換成經審查的整合 commit 與正式 registry／safe RGB。核對 #80 真實取圖端到端、Agent 設定與 Q3 parse provenance。
5. 在正式來源獨立跑 Demo／審核網址、1/2/4/8 格、兩種播放模式、Q3 非 PARSED、暫失／硬切／return、被拒提交／全 session 兜底、replay、色覺模擬與灰階檢查。寫 `Q1Q5_BROWSER_ACCEPTANCE.md`；本稿不代寫結果。
6. 組員按 #146 文件出題／答案；正式 #147 包與 #128 標註、#129／#138／#89 評分凍結輸出後再對照。PILOT／SYNTHETIC 不進正式分母。
7. 依實際畫面改寫本草稿旁白，附新的 screenshots／hash／run／clock／參數／code commit。人工／使用者驗收結果保持 NONE，直到本人留下紀錄。

## 5. 目前證據索引

全部 LOCAL：`~/amidst-artifacts/q1q5-staging-20261021/`。

- T1：`119-focused.tap`，48 PASS；原 #127 15 個實際 domain 回應報告 `119-conformance.json` 為 624 PASS／69 FAIL／18 缺 context；不是全通。
- T2：`120-focused.tap`，31 PASS；Q1 四狀態、Q3 四狀態及格數／分頁圖。
- T3：`121-focused.tap`，26 PASS；五個關鍵時點、拒絕與兜底圖；三份合成 session 已實際播到終點，短 session 可重播。無 RGB 的畫面保持 MISSING。
- T4：`122-focused.tap`，31 PASS；`122-browser-isolation.json` 為實際 Application HTTP Demo/Review 本文一致、output hash 一致、Demo 無 review 程式／預期檔網路請求。`122-browser-export.json` 是 FICT_UI_CONTROL_TEST 控制測試，重新讀檔 hash 通過，不是組員 T/F。
- 原 kit 自測：`122-kit-selftests.xml`，223 PASS；只證原 kit 自己的機械案例，不消除上述實際 domain FAIL。
- 後端：`112-focused.xml`，37 PASS；#174、#175、#180 的 mixed live/recorded 修復已發布並保留 Draft。
- 最新可啟動 source 組合：`engineering-qa-v3/COMPOSITION.json`。正式 r004、Ollama、獨立瀏覽器與研究接受度仍未驗證。
