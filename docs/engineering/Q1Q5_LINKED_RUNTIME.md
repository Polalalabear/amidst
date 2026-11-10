# 同源 RGB 工程條線

公開 locator 約定：`$AMIDST_ARTIFACTS` 代表審查者自行指定、canonical 絕對路徑的 LOCAL 證據根目錄，`$AMIDST_SOURCE`／`$SOURCE` 代表按 composition 還原的工程，`$AMIDST_PYTHON`／`$AMIDST_PYTHON_ENV` 代表既有 Python executable／環境。這些是去識別化 locator，不宣稱其他機器已存在對應資料；先取得相同 hash 的 LOCAL 檔案並設定環境變數。GitHub 只有公開程式與精簡收據，完整 RGB、錄製、模型 wire 與原始命令紀錄仍為 PRIVATE／LOCAL。文中的歷史數據未因路徑去識別化而重跑。

Issue #202；SYNTHETIC 工程控制，不是正式資料、身分或正確性驗收。

`run_q1q5_linked_baseline.py` 分三個顯式階段：`rgb` 固定來源 PNG、產生新的
960×540 BILINEAR RGB 與逐幀 hash；`index` 只讀安全 RGB manifest／像素，
由官方 RT-DETR 產索引；`cases` 要求操作員提供索引中實際 person observation ID，
產生查找／持續追查案例及綁定同一索引的 Qwen3 runtime。
每個輸入都需要檔案 SHA-256；每個輸出都是新的目錄。產製 prompt、排程、actor
及評估答案不交給索引或查詢。生成的兩張靜態圖只測工程流程，不能證明跨鏡身分。

索引程序退出後，再使用既有 `run_q1q5_baseline.py` 的 serial case/profile worker，
兩種 profile 使用相同 RGB、索引、圖、時鐘、參數及案例。Qwen timeout 保持原預算；
RULE fallback 與 LLM 成功分開記錄。首次與重複呼叫、離線 audit replay 沿用既有量測。

stage observer 是可選的旁路。沒有 observer 時輸出不變；有 observer 時，索引及
領域 hash 仍完全相同。forward fps 只計成功 CPU forward 幀數／所有 forward
耗時；不是端到端或畫面 fps。巢狀階段不可加總。RSS 是指定 PID 的取樣峰值，
不同程序峰值不可相加；swap／vm_stat 保存原值。無法量測的 display／實體 VRAM
峰值及正確性保持 null。

## 2026-10-24 實際工程結果

固定新合成 PNG，20 幀真 RT-DETR；7 筆 person 觀測且 red=STRONG。
CPU forward 6143.507415 ms / 20 幀 = 3.255469 fps；完整 index build
6739.034458 ms，model load 2370.439917 ms。取樣 caller RSS 峰值
784678912 bytes；程序 lifetime peak 另存。這些不是正式影像成效。

同一索引的查找／追查 × Qwen／RULE × 首次與兩次重複，共 12 樣本 COMPLETE，
24 次 stage replay 一致；兩 profile 的追查每次切鏡一次。Q3 6 次及 Q5 3 次
真呼叫皆 PROVIDER_TIMEOUT，LLM 採用 0，RULE 接手。正確性與正式 LOST
分類未核定，保持 null／synthetic policy。最初配置失敗錄製另外保存，不併入成功分母。

63 focused 通過；新增六個 Python 檔 Ruff 通過。LOCAL 原始量測位於
`$AMIDST_ARTIFACTS/local-work/amidst-baseline-line-20261024-01a16c37/`（最終持久包另記）。
