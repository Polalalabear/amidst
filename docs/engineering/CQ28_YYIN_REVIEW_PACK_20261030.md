# CQ-28 s1 審圖框架（#319）

狀態：程式與 SYNTHETIC 驗收已交件，正式包與發送未核准。既有 #317 的 manifest version / eligibility 待決不變；`build_pack` 預設仍 `CONTRACT_UNSELECTED`，只有明確 `synthetic_only=True` 才能建測試包。

## 範圍與來源

- 在 #361 的 `codex/cq27-yyin-main-pack` 分支接續；#349 的疊圖依賴以 feature merge commit 納入，PR base 維持 #240 的 `claude/yyin-q1q3-pack-design`。
- 依賴未經 Claude 複審：#349@79b34e33975a0e420d64b2fd994cbac97e92de7b、#294@0c34287b0b0c21c672f863fd281934f37e8aa24b、#361@e7edc985c83357f48bca9a67c00558aa95fac0a8。
- `review_payloads` 先驗 receipt SHA、三張圖 SHA、問題順序、相機、選項與來源邊界，再讀取固定 SVG；不修改來源。非合成唯讀檢查綁 #349 receipt `55ef71c6fe13d5d9ceef30d35788da6d7764307185f77fd858562776fd586023` 與修正後圖來源 #294。
- 三題分別問 WIDE 漏標門、BRANCH 轉角範圍、WIDE 下緣。A/B/C/都不是/看不出來及備註只記錄意見，不改圖或核准設定。
- 包內 SVG 名字提議為 `s1/s1-1.svg` 至 `s1/s1-3.svg`，保留來源檔案 bytes。正式打包 gate 未開；自測只產 tiny SYNTHETIC SVG，不複製真實圖進 fixture。

## 介面與回覆

`build_pack(..., s1_inputs=None)` 原本 s2-only 行為不變。明確傳 s1 inputs 才增加審圖頁、固定三題 CSV、README 15–20 分鐘估計及主頁連結。CLI 同步提供 `--s1-inputs`。LOCAL inputs 僅含 `path` 與 `receipt_sha256`；不是新 authority 或正式契約。

審圖頁可離線載入 DATA script，匯出 BOM/CRLF CSV 或重新匯入。回覆名 `RETURN/審圖_yyin_YYYY-MM-DD.csv`；缺答、都不是/看不出來缺備註時加 `_INCOMPLETE`。原始 `s1/確認.csv` 與 `templates/s1.csv` 是不可修改的空白 payload，既有 manifest 的兩個 editable files 完全不變。s1 三欄 `題號/選項/備註` 僅是本議題提議介面及明確 test-only profile，不宣稱已核定正式 wire。

`tools/verify_pack.py --s1-returned-csv <LOCAL回覆>` 獨立檢查表頭、三個固定題號、閉合選項、公式字元與缺答；無論答案為何都 `answers_verified=false`。不匯入評分、圖或參數。Python/JS 都保留引號及換行備註。

## 實際驗證

- `AMIDST_REQUIRE_IMPL=1 AMIDST_YYIN_BUILDER_INPUTS=<LOCAL SYNTHETIC inputs> python -m pytest -q tests/q1q5/test_check_handoff_pack.py tests/q1q5/test_yyin_main_pack.py tests/q1q5/test_yyin_review_pack.py`：64 passed，0 failed/skipped。
- `node --check src/amidst/q1q5/yyin_main_pack_assets/review.js`；11 個 Node assertions：BOM/CSV roundtrip、缺答、公式、固定題號、引號格式。
- `python scripts/check_handoff_pack.py --pack <LOCAL SYNTHETIC zip> --profile yyin-main --manifest-sha256 <receipt pin> --profile-options <LOCAL SYNTHETIC options> --profile-sha256 <options pin>`：目錄與 ZIP 均 VALID，scope `S1_S2_SYNTHETIC`；production profile UNSELECTED、release false。
- 瀏覽器在 loopback 載入合成頁，匯出兩題回答、第三題留白，再匯入還原引號/換行備註。隨包 verifier 判第三題 incomplete、answers_verified=false。
- `python scripts/check_architecture_guard.py`：NOT_RUN（#307 尚未交付）；#127 kit NOT_APPLICABLE（無產品錄製或 replay 輸出）。
- 未渲染、未讀原始 Blender、未發包、未修改權威圖/契約、未取得正式答案或正式驗收。

精確 LOCAL artifacts 與 hashes 見 `docs/history/YYIN_REVIEW_PACK_20261030.json`。測試 framework 的 manifest/ZIP hash 是合成產物，不是 yyin 正式包 pin。
