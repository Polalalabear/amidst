# 最小 Q3 候選 v1：一次審核材料

Refs #198、#192、#89。八個候選問題已先固定文字、順序、ID 與 bytes hash；每類一題。這是 Codex 的 AI 草稿，沒有給受測 Qwen 出題、答題或調 prompt。`configs/q1q5/q3_minimum_v1.public.jsonl` 只含 id/text，可作未來推論輸入；`q3_minimum_v1.freeze.json` 與本 CSV 為 evaluation/review 端資料，不送進推論。候選固定不等於獨立人工選題或正式凍結。

使用者可在同一輪驗收中逐題保留或修訂，獨立填寫 CSV；組員不必改程式。保留原版，回交填好的 CSV、問題/不確定/未完成清單與完整資料夾或 ZIP。這份新包不改正在進行的 yyin 圖/ROI/HSV 審查包，也不要求標記組員立即完成60題。

1. `keep_or_revise` 填 KEEP/REVISE/EXCLUDE。修訂文字填 reviewed_text；不確定寫 notes，勿猜答案。修訂/排除會建立新版本，不能沿用舊 hash。
2. 依固定的合法 catalog/run/clock scope 填 expected_status，與完整 expected_llm_output、expected_structured_query JSON（沿 #89 既有 schema；非 PARSED 的 structured_query 填 JSON null）。缺 scope 或答案保持空白，不能拿 parser/Qwen 的預測當標準答案。
3. 填 scope_ref/scope_sha256、reviewer/reviewed_at。CAM_W1 只來自目前安全相機 catalog；若正式授權子集不含它，必須另版改題。相對時間題也須先確認是否是當版支援語意，不能自行改成某日期/WALL時間。
4. 正式輪次前，由獨立審核者確認八類及精確答案，凍結公共文字、順序、context/clock、selection 與獨立 expected 收據；未完成時 formal_run_allowed 維持 false。這輪只是固定候選，formal_rows=0，評分結果/accuracy=null。

AI 草稿可以被採用，但必須經人工核對；Qwen 不讀答案/類別/筆記，推論只讀 id/text 及合法 runtime context。正式模型輸出先凍結再用獨立 expected 評分，沿既有 q3_parse_eval.py，不新增自訂正確率門檻。RULE fallback 不計 LLM 成功；同題組比較只換一個因素。八題是第一輪最小子集，不取代 #89 的完整60題工作。

本交付只有資料格式、交叉欄位、hash 與隔離檢查；沒有執行這八題、產生正式答案、獨立人工核定或正式Q3成效。所有新增檔隨 B/Draft 發布供一次驗收，不 merge。
