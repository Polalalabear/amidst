# Codex-W 支援資料與盤點交付（2026-11-24）

狀態：Codex 已完成，待 Claude 審查。Draft [#702](https://github.com/Polalalabear/amidst/pull/702)，分支 `codex/feat-support-data`，base main。Refs [#704](https://github.com/Polalalabear/amidst/issues/704)、[#684](https://github.com/Polalalabear/amidst/issues/684)、[#700](https://github.com/Polalalabear/amidst/issues/700)。

## A1：8CAM／預錄 est_xy（既有分支，另案交付）

Draft [#623](https://github.com/Polalalabear/amidst/pull/623)，head `9f3871f90263f0f1c4d27414687ba08908b8ca27`；merge `62aba25bfc182934b0628086dd6801239dd0069c` 的第二parent是指定main `ada45f31eba1f31f772d023e98816f476dbac234`。未rebase／force-push。25 focused passed、7 skipped；實觀測投影replay 1 passed；Node模型53 passed；CI checks 2/2 success。服務／browser因既有8GiB門檻無法完成，舊失敗log保留。完整命令、來源與可見3D限制見該PR及其 `WORKBENCH_RECORDED_ESTIMATE_20261118.md`。

## B3：指定 main 換 pin gate

交付commit `eafe94851a2a3b24ff2ac91d01e114b1f6b53d4f`。完整收據與命令見 [GATE_PIN_20261124.md](GATE_PIN_20261124.md)。獨立clone detached `ada45f31`，預定port8797。workbench Node579 passed；LIVE Node148 passed／2 skipped；Python289 passed／1 skipped／1 failed（磁碟）。Dependency與服務啟動失敗，後續HTTP／browser／Agent檢查未跑，RESULT逐行FAIL。**整體FAIL，不能換pin。**付費呼叫0。

## C1：E5 原數字摘錄

交付commit `100accc09f0c5d763ab32e24cb5e3dca2f6023ba`；[E5_NUMBERS_TABLE_20261124.md](../evaluation/E5_NUMBERS_TABLE_20261124.md)。表內1,834列S1原值與CI逐JSON pointer核對相符，缺漏數值欄0；S2既有組別與逐段表照抄。以Python標準庫 `json`（`parse_float=Decimal`）、`hashlib` 讀既有JSON／Markdown，沒有呼叫scorer、run、模型或讀取原始GT／RGB。驗證是從表列pointer解析回原JSON，逐一比對原值與同名前綴 `_ci`，並列舉來源所有數值欄確認覆蓋；不是重新算指標。

S1/S2檔案hash、大小、相對路徑已在表§1；§5費用維持帳本上界19.132與來源估算約USD7.5。缺CI／樣本數欄標UNKNOWN，沒有從陣列長度、true數或token推算。#698在取資料時已合併d52ce2f0，與派工時描述的審查中不同；原報告未改。

## C2：PROGRESS 補列留言草稿

[完整草稿與實際產出](https://github.com/Polalalabear/amidst/issues/674#issuecomment-7107263602)。`gh api graphql`一次用43個 `repository.issueOrPullRequest(number:...)` 別名查#656–#698的原標題、類型、狀態、Draft、base及mergeCommit.oid；27PR／16Issue，缺號0、重複0。每項只列一個主分類／狀態；所有merged PR都有完整merge SHA，issue用N/A。未修改PROGRESS.md。草稿分類供Claude／協調者批次確認，不全面重整#1–#655的舊資料。

## C3：CODE_DOC_MAP 增量清單

交付commit `ffe793f3f84f00a0237eb620c658f730ad11d9a5`；[CODE_DOC_MAP_DELTA_20261124.md](../index/CODE_DOC_MAP_DELTA_20261124.md)。原表最後更動 `ea31b643` 到main `d52ce2f0` 的91檔（59新增／32修改），20項文件對應UNKNOWN。只用Git名稱清單與文件字串引用；沒有讀取或改寫禁止範圍的程式內容。原CODE_DOC_MAP.md未改。

```sh
git log -1 --format='%H %cI %s' -- docs/index/CODE_DOC_MAP.md
git diff --name-status ea31b64396b555a49cc6b9b06ff11f0536c2aa06..d52ce2f0
rg -n -F -f <changed-path/name-patterns> docs --glob '*.md'
git diff --check
```

逐列清單比對缺漏0、重複0，文件相對連結存在。未跑程式測試，因為只新增索引文件。

## C5：owner 標籤盤點留言

[完整差異與實際產出](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7107360394)。

```sh
gh issue list --repo Polalalabear/amidst --state open --label owner:codex --limit 500 --json number,title,body,labels,updatedAt,url
gh issue list --repo Polalalabear/amidst --state open --label owner:claude --limit 500 --json number,title,body,labels,updatedAt,url
gh issue view 93 --repo Polalalabear/amidst --json body
```

再以 `gh api graphql` 讀12個帶ready／blocked／in-progress issue的最後5則留言。18個open owner issue，6項標籤／狀態差異；#659另列scope待確認。#676有Codex-L當前認領，不判成無人工作。未修改被盤點issue的標籤、狀態或關閉它們；未查他人的本機工作，不能僅以時間推定停工。

## LOCAL 證據與重現邊界

- LOCAL `local/evidence/codex-w-20261124/MANIFEST.json`，SHA-256 `2e77ed0f7da23530c215241a5bdaee4d8a3921991223b09a536cb7e0f9d1babf`，列25檔／833,341 bytes（manifest本身另計）。涵蓋A1測試與原始失敗、C1逐值核對、C2 gh快照、C3名稱／文件引用及C5狀態快照；各檔SHA-256在manifest。
- B3證據另見GATE_PIN文件的SHA256SUMS／RESULT hash。這些皆小型log／JSON／文字，不含新增媒體。
- 測試／清單可依各節命令重做，時間與GitHub狀態可能改變，不保證log逐位元相同；E5表可以從已存在的S1/S2/S3檔案只讀重建。AO原執行要付費，本次沒有重跑。
- 沒有付費呼叫、Blender render、detector inference、8785 pin變更、8791重啟或合併。所有寫作在自己的shared scratch clone；交付後移除clone。凍結demo仍是c988ed60。
