# 協調者交接 2026-11-28

> 寫入者：協調對話（Claude Opus 5.5，2026-11-28 接手 20261127c）。main @`0b8b400a`。**新的協調對話全程用繁體中文回覆**（D255）。
> 下一個決策號：**D418**。決策記錄在 #93，更新紀錄 append 到 #674。

## 0. 先讀

1. 本文件。
2. #93 的 D416、D417 留言。
3. #780（E8 總 issue）：設計審查留言 https://github.com/Polalalabear/amidst/issues/780#issuecomment-7225171977 、W2 結果留言 https://github.com/Polalalabear/amidst/issues/780#issuecomment-7225160831 。
4. #767 的協調者分析：https://github.com/Polalalabear/amidst/issues/767#issuecomment-7224614486 ，以及 D416 補記 https://github.com/Polalalabear/amidst/issues/767#issuecomment-7225067592 。

## 1. 本次決策（摘要）

- **D416**：laya 不進 LIVE demo，demo 只用 B1。E7 的 laya 輸給規則：錯人 375.2／323.8 s 對 B1 114.0 s，多出的秒數 79%／86% 是錯鏡頭。原因在 E7 的**題目設計**：
  - 請求沒有「找紅色」、上一個位置、鏡頭連通和圖片；
  - laya 從不回答 NOT_VISIBLE；
  - 72%／65% 選清單第一個候選。

  補記：E7 輸入少於 B1 和 API Agent，**不能**拿來回答「Agent 是否優於規則」。
- **D417**：做 E8 完整版（海報延後 1–2 天）。GT 用折衷：第一部分在 Colab 只放標籤表；第二部分回 Mac 評分。分工改為 **Claude 主做、Neon 輔助、Codex 只拿不急的 issue**，取代 D376。
- **使用者新規則**（已記成記憶 `reuse-existing-before-new`）：開 issue、列工作或寫 brief 之前，先查既有的 issue 與 **GitHub main** 上的檔案（本機 `~/amidst` 是舊的 pin，會落後）。已有的就註明「可沿用修改」，不重複新增。
- 使用者要求：P0（研究結論與 E8 數據）全部由 Claude 做；要使用者審查或按卡的項目都要交給使用者。

## 2. 所有工作（依類型）

### 2.1 研究：E8 與 E7（最優先）

| 項目 | 預計產出 | 進度 | 卡點 |
|---|---|---|---|
| E8 W1 設計與預登 | `docs/evaluation/E8_DESIGN_V1.md` | 已 APPROVE，附 4 項必改（`claude/feat-e8` @`d4cebd12`）：沿用清單、merge 修正後的 e7 分支、Qwen L0 時間重估、在 #767 補 laya 截斷發現 | — |
| E8 W3／W4 打包、notebook、閉迴路、Mac 評分、E8 報告 | 一鍵 Colab 包（A100 約 2–4 h）、`e8_score_run.py`、`E8_REPRO`／報告、Draft PR | session **e8-main**（`local_13219d3d-b2e2-4874-a8b6-e95388a7eb8a`）實作中 | 依賴 `e7_replay` 的部分要等 #769 修好 |
| E8 W2 離線底線 | #780 留言＋LOCAL `e8-offline-b-20261128/e8_w2_offline_baselines.json`（`7cd069bc…`） | **完成**。「永遠選第一個」370.2 s ≈ laya_text；「第一個紅色」278.6 s 比兩版 laya 好，但仍輸 B1 164.6 s；信心門檻只是用失聯換錯人（探索性） | 腳本在共享筆記資料夾，由 e8-main 收進 E8 PR |
| 使用者在 Colab 跑 E8 | `e8-run-<日期>.zip` | 等 W3 交包 | 使用者操作 |
| E8 PR 正式審查 | Sonnet 審查（加上 complex code 的 Opus 點） | 未開始 | 等 PR |
| #769 E7 後續（#766／#767／#768） | 合併進 main | Opus 裁定 NEEDS_CHANGES，四點見 https://github.com/Polalalabear/amidst/pull/769#issuecomment-7225149727 。session **e7-followups**（`local_8fd48bcc-9d15-4ab1-a4fc-511a31912f8f`）正在修，CI 紅 | 修完交給 **769-e7-sonnet**（`local_484e7210-3954-4160-90f9-4a59a3b0ca08`）複審；CI 綠後問使用者合併；之後把修正後的 SHA 通知 e8-main |
| E7 分析文件進 repo | `docs/evaluation/E7_LAYA_ANALYSIS_20261128.md` | 已交給 e8-main 收進 E8 PR | — |
| #781 GPT 組（擴充 `e6_arms_run.py`／`aopen/arms.py`） | Mac、ApiGuard，結果與 E8 並列 | blocked（owner:codex） | 等 E8 輸入組裝合併；預算剩 USD 41.78 |
| #782 E8 獨立複核 | #780 留言 | blocked（owner:codex） | 等 E8 結果 |
| #765 E6 單點配對（R-N 狀態） | — | deferred。E8 改用 B1 狀態，**不**由 E8 關閉 | — |

### 2.2 報告與海報（Neon，輔助）

| 項目 | 預計產出 | 進度 | 卡點 |
|---|---|---|---|
| #734／#776 E6 數字回填 | `neon/feat-report` 的 PR | 設計 APPROVE，附 4 項必改；已給使用者可貼的派工文字 | 等 Neon 開工 |
| 海報版面（原 #779，已併入 #734） | 放大架構與流程圖、縮減做法與評估、結論只留關鍵圖 | 意見已貼到 #734 | Neon |
| E7／E8 段 | E7 照 D416 措辭；E8 先放 PLACEHOLDER，之後從結果 JSON 經 `report/figures/build_figures.py` 產圖 | — | 等 E8 數字 |
| #479 LaTeX 實驗紀錄 | 補 E6、E7、E8 | 未動 | 等 E8 |

### 2.3 8785 demo 與 LIVE

| 項目 | 進度 | 卡點 |
|---|---|---|
| #773 AC7 B-05 雜湊 | 診斷 PR #778 已合併（`0b8b400a`），issue 開著 | 要決定 AC7 是否接受這個差異（D313 的逾時參數改變了雜湊） |
| #770 AC2 時鐘解析 | Codex 進行中（#775） | Codex 額度 |
| #771、#772 AC3／4、AC6 前台 | ready（owner:claude） | 排在 E8 之後 |
| #675 Agent 選項接線 | blocked（D414、D416） | 等 E8 結論 |
| #735、#676 LIVE 收尾、藍衣 | Codex | Codex 額度 |

### 2.4 流程與整理

| 項目 | 進度 | 卡點 |
|---|---|---|
| #777 文件 PR（總帳 D411＋PROGRESS 補到 #774） | 開著，沒審 | 審查後問使用者合併；之後把 #775–#782、D416–D417 補到 PROGRESS（接在 #777 後面，不另開） |
| 開放認領規則（暫定 D418） | 使用者還沒決定哪些項目開放 | 等使用者 |
| 封存對話 | 見本次交接訊息 | 使用者操作 |

### 2.5 Codex 與 Neon 的任務

- **Codex**（額度用完，等恢復）：#770 → #735；#781、#782（blocked）。
- **Neon**：#734（含海報版面）、#776。

## 3. 使用者要審查或按卡的事

1. #769 修好、CI 轉綠後的合併同意。
2. E8 的 Colab 執行（A100），以及之後的 E8 PR 合併。
3. #777 合併；#773 的 AC7 判斷；D418 要開放認領哪些項目。

## 4. 限制與注意

- `~/amidst` 是 8785 的 pin（落後 main），不在裡面改檔、切分支或 fetch；寫檔一律在 scratchpad 精簡 clone 裡做。目前磁碟剩約 15 GiB。
- 合併、刪除、改 pin、超出預算的付費呼叫都要先問使用者（AskUserQuestion，2–3 個選項，推薦的放第一個）。
- 用量：交接時 5 小時額度用了 56%、每週額度 74%（每週額度在 2026-11-29 20:00 +08 重置）。
