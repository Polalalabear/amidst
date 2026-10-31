# #235／#236／#234 合併後備註修正

2026-10-27，C2。既有三PR經#231已MERGED，本修正另開PR，不改它們的歷史分支或既有LOCAL包。

- #235 L1：新增hash sidecar，綁收據本身、generator、CLI、test四檔bytes SHA與兩圖content hash，沒有自雜湊循環；L2移除重複D81標題。M1明列逐條核准與保守值兩個選項，仍由使用者於G4決定，不在此改loader／candidate或凍結圖。
- #236：關鍵字尾端用`\Z`，不再把單一尾端newline視為結尾。補充原有額外規則：若人工標註含Q1 case，人工Q3狀態只接受PARSED或未提供；否則整列`CSV_ANNOTATION_STATUS_MISMATCH`，不輸出部分答案。此為既有檢查的說明，非本次新增限制。歷史metadata中#238舊時鐘值明示為當時未核定Draft／已被D89取代；更新入口仍以#238經複核合併的D84/D89 metadata為準。
- #234：新生成README加D83「P1只人工閱讀、不補importer、不進正式指標」；pack builder封裝前掃描全部text payload的private absolute locators（拒絕時只報相對檔名，不印出private值）。SOURCE/BUNDLE及其他生成JSON排序、UTF-8寫入；README/HTML/launcher明確UTF-8。RETURN的原表單與空白樣板列入MANIFEST，使用者由表單下載新的具名回交CSV，原模板不覆寫；新增回交檔不影響原始manifest驗證。

這些改變只作用於之後新建包；舊P1 v4／C26 pins及三包raw source不改，不能以本PR測試宣稱實體包已更新或AC7通過。scope／clock／圖原始asset不改，未渲染。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 新Draft `codex/q1q5-merged-review-notes`；base `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`，精確head見PR。
- Files changed: importer與focused test、portable_pack與focused test、R004_GRAPH_RECEIPT、hash sidecar、歷史formal metadata、本文件（8檔）。
- Commands run and results: 離線uv/Python `pytest -q -p no:cacheprovider tests/unit/test_team_review_pack.py tests/q1q5/test_portable_pack.py tests/q1q5/test_p1_workbench.py`：102 PASS；變更Python檔`ruff check --select F,UP,B` PASS；4個檔案SHA與兩圖content SHA重算PASS，原8個graph JSON未改；`git diff --check` PASS。
- Artifacts: 公開hash sidecar；沒有新ZIP、RGB或錄製。
- Verified: 尾端newline拒收；private locator scanner；deterministic UTF-8 JSON；RETURN模板改動遭manifest拒絕、新具名回交不影響原pin；M1仍未選。
- Not verified: 完整portable實體包重建／整包實際掃描、browser、CL-4、#127／AC7、G4、正式研究指標。
- Deviations, UNKNOWN items and follow-ups: 實體包更新需後續新建，不重封舊包。SOURCE/BUNDLE byte hash會依新build重發，不承諾等於歷史C26。
