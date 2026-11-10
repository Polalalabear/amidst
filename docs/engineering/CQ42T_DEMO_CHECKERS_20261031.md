# CQ-42-T demo 腳本／彩排格式檢查器

2026-10-31（Asia/Taipei）。#340 的 test-first 工具；主交件為 #124 demo 腳本與 #339 彩排。base staging `434e57922a24d2422226871c0bb672dc7bc3584b`。本次不產生真實彩排，也不記錄 #346 使用者接受。

## 介面與驗證邊界

兩個本任務明列的 schemas 位於 `docs/agents/schemas/demo-checklist.v1.json` 與 `demo-rehearsal-record.v1.json`，均為 **PROPOSED 格式**，不是核准 authority。closed objects 拒絕額外欄位、未知版本／enum；輸入拒絕重複 JSON keys、NaN、非 canonical 路徑與 symlink。使用 Python 標準庫，不下載 JSON schema 或執行外部工具。

共享 `scripts/demo_record_checks.py` 僅實作這兩份 schema 用到的有限 JSON Schema subset；遇未實作 keyword／type 即拒絕，不聲稱支援通用 JSON Schema。

checklist 包含 schema_version、source_ref 及 items（id／title）；fixture_role 只用 SYNTHETIC_ONLY。record 另需 checklist 原 bytes SHA-256、每項 id／result／evidence 及 fallback a/b/c。每項可附 note 與 claude_review_status；省略時報告明列 NOT_REVIEWED，原輸入不回寫。REVIEWED 只是申報值，不由 checker 驗證 Claude 身分或審查。

彩排逐項必須恰好涵蓋 checklist：缺項、未知項、重複項拒絕；result 限 PASS／FAIL／NOT_RUN。PASS 必須至少一個 SCREENSHOT 或 OUTPUT 的64位小寫hex SHA-256。這只驗 hash 的存在／格式；**不讀取或核對證據原檔，也不證明操作真的發生**。報告明列 REPORTED_ONLY_NOT_READ_OR_VERIFIED。FAIL／NOT_RUN 可保留為一般項目的實際結果；VALID_RECORD_FORMAT 不等於 demo 通過。

fallback a/b/c 必須各一筆且不是 NOT_RUN；演練失敗可如實記 FAIL。名稱對照 #346 D-02：a Ollama 停止→replay、b API 關閉→啟動器重啟、c 正式輸入缺→P1並標示。checker 驗證紀錄完整性，不判定這三種故障真的被製造／恢復。

Markdown 格式以 `## B-01 標題`（亦可 C-/D-）開每一步，其下各一行 `操作：…`、`預期：…`、`fallback：…`。每步 ID 必須在傳入 checklist，重複／未知 ID 或缺欄／空欄拒絕。縮短版可以只涵蓋部分清單，報告列 uncovered_checklist_ids，不冒稱全程完成。

GT／劇本值檢查拒絕已知結構欄位，以及正文的 t_X／t_N、gt_*、decision/entry window、評分窗等帶數字賦值（含全形／反引號形式）。「檢查 GT 隔離、評分窗不顯示」等無值說明可保留。這是具名欄位／賦值檢查，不能識別所有自然語言改寫或證明整個資料流隔離；#307 及實際 source audit 仍需獨立執行。

## 依賴到位後怎麼跑

以下為 #340 原列命令，尖括號由主任務提供精確實際路徑，不是假造已交件：

```sh
python scripts/check_demo_script.py --script docs/agents/Q1Q5_DEMO_SCRIPT.md --checklist <清單 JSON>
python scripts/check_demo_rehearsal.py --record <彩排 JSON> --checklist <清單 JSON>
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_demo_rehearsal.py
```

實際執行 Python 仍依專案規則以 `uv run python`；本機重用既有 Python 3.12.12 環境，完整 focused 命令在 curated receipt。CLI 成功 stdout 是 JSON 格式驗證報告、exit0；拒絕 stderr／exit2。schema 或 fixture 成功不取代前兩行對真實主交件的檢查。

43 個 focused 自測涵蓋：六項正例、三個檔案反例、closed schema／checklist pins、結果保留／review default、步驟映射／三欄、私有值誘餌、schema drift、非canonical／symlink、五個實際 CLI 子程序。`AMIDST_REQUIRE_IMPL=1` 下被測 checker 必須存在；目前所有 checker 已隨本 -T 實作，無 missing-implementation skip。

## Registry 與未驗項

**#307 schema registry 尚未交付，登記接線 NOT_RUN。** 需要協調者先解決 #307 的 authority drift／baseline 驗收衝突，再由該任務交付 registry 介面。本次不自行發明 registry 路徑、欄位或豁免；兩份 schema 的精確 bytes SHA-256 收在 `docs/history/CQ42T_DEMO_CHECKERS_20261031.json`，供後續採納／登記時核對。這部分保留 pending，不能宣稱架構守門或 registry PASS。

ARCH `python scripts/check_architecture_guard.py` NOT_RUN；#127 recorded kit NOT_RUN（沒有新product recording）。未驗真實 #124／#339 產物、證據bytes、browser／故障演練、Claude review、使用者接受、正式研究結果。無原資產操作、render／inference、merge／ready、發包或 main 修改。
