# 協調者交接（2026-11-23 第二份）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `ab51e5ac`（#686 合併）、更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 共 47 則。
> - 本文件是快照。現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D359**），更新一律追加在 #674。
> - 上一份交接：`docs/agents/COORDINATOR_HANDOFF_20261123.md`。

## 1. 一句話現況

E3 的結論是：在依附規則的整合方式下，看圖 Agent 沒有勝過規則。使用者因此改做 **E5：完全開放的 Agent 對規則**（A-open，D356），只用資源限制約束 Agent。E4 已停，資料保留成探索性附錄。

E5 的預登記和介面契約在 PR #685，目前等 Codex 回覆「契約確認」。實作會在 Codex 的新對話裡做。海報和簡報素材已經做好，放在 LOCAL 資料夾。

## 2. 工作方式（使用者 2026-11-23 指示）

- **協調者主對話只做決策。** 實作、審查交給子 session，按 CLAUDE.md 的模型分級表派工。
  - 例外：使用者要求審查直接在主對話做時，照使用者的意思。
- **要貼的文字放在回覆的 code block。** 給 Codex 的訊息、給使用者的指令都一樣，每條只給一次。
- **工作後的文件只做必要更新。** 大更新（PROGRESS 補列、index、CODE_DOC_MAP）之後再一起做。
- **合併規則（D305）：** 審查通過、CI 綠燈就用 merge commit 合併。UI 改動要先給使用者看截圖。
- **#676 的 Codex PR #690 在 E5 結束前不能合併。**
- **預算：** 上限 USD 100，累計到 90 前不用問。目前累計約 **USD 58**。E5 的費用上限是 USD 25，每次執行都要先 dry-run。
- **磁碟：** 剩約 9.7 GiB。開第三個寫入 session 前至少要 9 GiB，剩 5 GiB 就停。

## 3. 所有工作（依類型）

### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [E5 #684](https://github.com/Polalalabear/amidst/issues/684) A-open（預登記＋契約） | `docs/contracts/E5_AOPEN_INTERFACE_V1.md`、E5 預登記 | PR [#685](https://github.com/Polalalabear/amidst/pull/685) head `0587ecf9`，CI 2/2 綠。協調者對三項待釐清事項的裁決已寫進契約：①API 分類 ②缺排名的表示法 ③OCCLUDED 維持條件。§4 評分和 §5 門檻沒改 | **等 Codex 在 #685 回覆「契約確認」**。協調者先看 `af71af55..0587ecf9` 的差異，確認只動到裁決的三項；Codex 確認後就合併 #685 |
| E5 實作與執行 | `decider.py`、`neutral.py`、`e5_run.py`，A-open × 16 段，報告 | 未開始 | 要等 #685 合併。由 Codex 新對話實作，Claude 審查（complex code，Opus 決定）。每次執行先 dry-run，費用上限 USD 25 |
| E4 | 探索性附錄 | 已停（D356）：跑了 10/48 次，花 USD 4.30，沒有評分。`claude/feat-e4` `f8f21afa` 保留 | — |
| F5 #659 論文 | 論文 md → PDF | 未開始 | 等 E5。E3 章節可以先寫（檔案不重疊時） |
| #623 預錄 est_xy／8CAM（Codex） | — | Draft，CI 綠，待 Claude 審查 | 暫緩到 11-25 之後（D344） |

### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| #676 顏色接線＋#675 LIVE Agent 啟用（Codex PR [#690](https://github.com/Polalalabear/amidst/pull/690)） | #676 Codex 已完成，待 Claude 審查。#675 的啟動和開關都驗證過了 | ①#675 的真實回應要等**使用者核准資料外傳**。②**E5 結束前不能合併** |
| #689 未接入的 run 拒絕 manual_seed（Codex，Closes #688） | Codex 已完成，CI 綠 | 待 Claude 正式審查（Sonnet medium） |
| #672 LIVE 追其他目標 | 設計在假設文件 §0.2 | 會改 advisor／scheduler，排在 E5 之後 |
| #633 LIVE 改 workbench-v2 風格 | — | 11-25 之後 |

### 3.3 研究紀錄、報告與發表

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| PR [#687](https://github.com/Polalalabear/amidst/pull/687) D358 引用更新（交接指向 20261123、F4 E3 報告、假設文件 §0） | Draft，CI 綠 | 待審查；審查通過後依 D305 合併。合併後再把交接指向改成本文件（小改動，可以併進下一個文件 PR） |
| 海報（A1 直式、可編輯 .pptx）與簡報大綱（open-slide） | 已完成，放在 LOCAL `local/evidence/presentation-pack-20261123/`，內容見 §5 | ①使用者從三張架構圖選一張。②結果數字等 E5。③簡報要依 `slides/OUTLINE.md` 寫成 open-slide 專案（Claude 製作，Sonnet medium） |
| #479 報告素材、#674 更新紀錄 | 持續追加 | — |

### 3.4 8785 demo

- 8785 的 pin 在 `c988ed60`（使用者 2026-11-23 核准；gate `local/evidence/gate-pin-20261123/RESULT.txt`）。
- main 已經前進到 `ab51e5ac`（#686）。要換 pin 時，跑 gate 再請使用者核准，不能自己改。

### 3.5 Codex 的任務

- **Codex 新對話（E5 專責）：** 等它在 #685 回覆「契約確認」；#685 合併後實作 E5。
- **Codex 舊對話：** #690（#676、#675）、#689、#623。

## 4. 新協調者的第一件事

1. 看 #685 的 `af71af55..0587ecf9` 差異，並查 Codex 有沒有回覆「契約確認」。有就合併 #685，在 #93 記 D359，在 #674 追加一則；還沒有就等。
2. 派一個 Sonnet medium 審查 #689 和 #687；審查通過、CI 綠就合併。
3. 等使用者選架構圖；派 Sonnet medium 依 OUTLINE 把簡報寫成 open-slide 專案。
4. #690 的資料外傳核准，要問使用者。

## 5. LOCAL 產物

`local/evidence/presentation-pack-20261123/`，約 5.3 MB，可以用 `scripts/` 重建：

| 項目 | 內容 |
| --- | --- |
| `poster/poster_A1_academic.pptx` | 594×841 mm，原生文字、圖形和圖表，約 0.9 MB |
| `poster/poster_preview_quicklook.png` | 預覽 |
| `slides/OUTLINE.md` | 12 頁大綱，從動機開始，Demo 錄影 3–5 分鐘 |
| `images/` | 14 張圖：三張架構圖、決策流程圖、五張決策點圖、兩張八鏡頭畫面、鏡頭覆蓋圖、兩張工作台截圖 |
| `scripts/` | `poster_pptx.py`、`arch.py`、`flow_png.py`、`poster_v3.py`、`posters_v2.py`（python-pptx 1.0.2、Pillow 11.3.0） |
| `README.md` | 待填項目和列印說明 |

決策點圖和場景圖的來源是 `local/evidence/e3-figures-20261123/`（#670）。
