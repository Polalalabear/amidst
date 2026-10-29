# CQ-27 主包框架與合成驗證

本交件只提供 s2 離線出題表單與可重現 builder；s0（#347）、s1（#319）仍缺。這不是可發送主包，也不是正式答案、核定或模型驗收。

## 建包門檻

#240 @2938bbb 的 §7 第10步要求正式 `version=v1`／`evaluation_eligible=true`，但同一段把 PROVISIONAL 輸入改用 `v0-pilot`／false 的選擇留給協調者。詞表仍 PROVISIONAL，不能以 `v1` 的 dataset-kind 推導正式接受；目前沒有相應決定。因此預設呼叫在寫出檔案前回 `CONTRACT_UNSELECTED`。`--synthetic-only` 僅用於明示 SYNTHETIC run 的機械測試；測試 manifest 的 v1／false 不是選定正式版本。U11 發包同意仍須另外記錄。

builder 逐一驗 source manifest、catalog、clock、run、物件清單及八張圖的 pins，拒絕 symlink、錯誤綁定、未選 PNG metadata 和既有輸出。它不改原始資產。所有維護者路徑與內部檔名留在 LOCAL 輸入設定；包內只有附圖、表格、介面及校驗工具。

## 合成重現

在本 PR 的精確 head、Python 3.12 環境執行，輸出路徑須為尚不存在的 LOCAL 目錄：

```sh
python3 scripts/make_synthetic_yyin_pack_inputs.py --output /private/tmp/CQ27_SYNTHETIC_INPUTS
python3 scripts/build_yyin_main_pack.py --inputs /private/tmp/CQ27_SYNTHETIC_INPUTS/inputs.json --output /private/tmp/CQ27_SYNTHETIC_A --synthetic-only
python3 scripts/build_yyin_main_pack.py --inputs /private/tmp/CQ27_SYNTHETIC_INPUTS/inputs.json --output /private/tmp/CQ27_SYNTHETIC_B --synthetic-only
cmp /private/tmp/CQ27_SYNTHETIC_A.zip /private/tmp/CQ27_SYNTHETIC_B.zip
AMIDST_REQUIRE_IMPL=1 AMIDST_YYIN_BUILDER_INPUTS=/private/tmp/CQ27_SYNTHETIC_INPUTS/inputs.json uv run python -m pytest -q tests/q1q5/test_yyin_main_pack.py tests/q1q5/test_check_handoff_pack.py
```

外部 checker 依 #359 的文件使用明示 TEST-ONLY s2 profile 與其 SHA；不能把這個 profile 視為正式發包規格。這次27檔 ZIP 的 SHA 與 manifest SHA 見同批 `docs/history/YYIN_MAIN_PACK_20261028.json`。兩次 bytes 相同，所有中文 ZIP entry 設 UTF-8 flag，時間戳依設計固定1980-01-01。DATA 使用指定 row_ids／row_groups／dropdowns／keywords／time_window／help_texts；兩端依同份資料顯示與檢查。

## 實際驗證與限制

- 嚴格 -T＋checker focused：50 passed。合成探針驗錯 pin、symlink、覆寫、預設 production mode 都拒絕，且不留下輸出。
- 包內 verifier 驗完整 payload，包括原始可填 CSV；只缺可補的 template 為 VALID_WITH_WARNINGS，原始CSV改編號、一般檔案改bytes都拒絕。
- 回件驗 closed 欄位、note-format.v2、人物目標、鏡頭 evidence、固定編號、公式與換行；缺必填／配額回 INCOMPLETE，不補猜。合成14列送既有 importer，原始回件 SHA 保留，全部停在 PRECISE_HUMAN_ANNOTATION_REQUIRED，queries/cases皆0。
- Node 15 項 UI assertion：CSV逗號／引號／CRLF、Unicode與全形分隔符、公式／換行、人物或無時間不補Q1、看不清範圍、換鏡頭後忽略舊evidence、反問與否矛盾拒絕。
- IAB於 localhost 實際填兩列合成句子、匯出 `_INCOMPLETE.csv`、改字再匯入恢復成功；匯出14列、BOM與CRLF，公式前綴拒絕。最終DATA重構後另驗載入／回填與反問＋否拒絕；下載CSV送verifier/importer亦正常。另給1列明示SYNTHETIC annotation，得到1列query且text逐字一致、eligible=false。這是 bounded browser check；未驗 yyin 電腦、Windows、跨瀏覽器或正式作答。
- 架構守門 NOT_RUN：#307尚未交付且有待決。#127不適用：沒有產生產品錄製輸出。未渲染、未執行推論、未發包、未核答案、未合併。

## 後續

協調者選定版本／eligibility 後，另以精確 pins 開放實際候選建包；補 s0/s1、重跑檢查，再取得 U11。同時保留 #240／#269／#350／#359 未經 Claude 複審的邊界。既有 team-review-pack schema、欄位、importer 與 v1 scorer bytes 沒有改動。
