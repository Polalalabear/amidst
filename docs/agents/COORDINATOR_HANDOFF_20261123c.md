# 協調者交接（2026-11-23 第三份）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `ada45f31`（#695 合併）、更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 共約 70 則。
> - 本文件是快照。現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D362**），更新一律追加在 #674。
> - 上一份交接：`docs/agents/COORDINATOR_HANDOFF_20261123b.md`。

## 1. 一句話現況

E5（完全開放的 Agent 對規則 B1）的預登記、契約、評分程式和實作都已合併，**AO 正式執行正在跑**。跑完就評分、寫報告，再決定要不要跑 AO-L。

### 今天合併的 PR

| PR | 內容 | 合併 SHA |
| --- | --- | --- |
| [#685](https://github.com/Polalalabear/amidst/pull/685) | E5 預登記與 A-open 介面契約（D360） | `396be050` |
| [#689](https://github.com/Polalalabear/amidst/pull/689) | 未接入的 run 明確拒絕 manual_seed（Codex） | `d4521ee9` |
| [#687](https://github.com/Polalalabear/amidst/pull/687) | D358 引用更新 | `e6b4e22e` |
| [#692](https://github.com/Polalalabear/amidst/pull/692) | E5 評分程式 `e5_score.py`＋測試 | `fe442470` |
| [#693](https://github.com/Polalalabear/amidst/pull/693) | F5 論文 E3 章節（新檔 `docs/paper/F5_PAPER_DRAFT.md`） | `901e5953` |
| [#694](https://github.com/Polalalabear/amidst/pull/694) | E5 A-open 實作（Codex；Opus 裁決 D361：GT 隔離、§4、N4 接受，N2 要修） | `4ab7bc10` |
| [#696](https://github.com/Polalalabear/amidst/pull/696) | N2 修正：AO-L 搜尋排除 EXPIRED 排名（AO-L 可以跑） | `24c2dce9` |
| [#695](https://github.com/Polalalabear/amidst/pull/695) | #677 LIVE UI/UX（使用者看過截圖；**還沒部署到 8791**） | `ada45f31` |

### 今天的決策

- **D359（使用者）**：#675 的資料外傳等 E5 結束再做；付費呼叫只要累計不會超過 USD 90 就不用問，每次仍然要先 dry-run 並記帳。
- **D360**：合併 #685。
- **D361**：合併 #694。

## 2. 工作方式

- **協調者主對話只做決策。** 實作、審查交給子 session，按 CLAUDE.md 的模型分級表派工。使用者要求審查直接在主對話做時，照使用者的意思。
- **要貼的文字放在回覆的 code block。** 給 Codex 的訊息、給使用者的指令都一樣，每條只給一次。
- **工作後的文件只做必要更新。** 大更新（PROGRESS 補列、index、CODE_DOC_MAP）之後再一起做。
- **合併規則（D305）：** 審查通過、CI 綠燈就用 merge commit 合併。UI 改動要先給使用者看截圖。8785 換 pin 和花錢超過門檻仍要問。
- **#690 在 E5 結束前不能合併**（會改變 B1 快照的來源雜湊，見 §3.2）。
- **預算（D359）：** 上限 USD 100，累計不超過 USD 90 就不用問；E5 這邊以 USD 89 為上限。每次執行都要先 dry-run 並記帳（`ApiGuard`）。
- **磁碟：** 剩約 9.3 GiB（使用者今天刪了 Chrome-headless 快取，清出約 5 GiB）。開第三個寫入 session 前至少要 9 GiB，剩 5 GiB 就停。
- 每個子 session 完成後都要在 #674 追加一則。

## 3. 所有工作（依類型）

### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| E5 AO 正式執行（[#684](https://github.com/Polalalabear/amidst/issues/684)） | 16 段 × K=3 的 A-open 結果、評分、`docs/operations/E5_REPORT_*.md`、`claude/feat-e5` 上的 Draft PR | **進行中**：3 個行程並行，上限合計 USD 25。由子 session 「E5 AO 試跑」（Claude Code session `local_073d1ce8-8722-42b4-b1c2-1d65cdac1305`）負責，跑完會自己評分、寫報告、開 Draft PR。試跑：E3-A1 K=1，30 次呼叫，格式退回 0，provider 錯誤 0，USD 0.312。開跑前帳本累計 USD 59.11（含試跑），加上 25 為 84.11 | 等執行跑完。報告 PR 目前還沒開（UNKNOWN 何時完成） |
| E5 報告的偏差段 | 報告裡的「偏差」一節 | 待寫（由上面的子 session） | 必須寫到：①N4 的讀法；②N5：`calls[].tick` 是生效 tick；③AO 用的是 `4ab7bc10`（N2 當時還沒修，但 offline 路徑走不到 N2） |
| E5 AO-L（H8d） | AO-L 結果 | N2 已修（`24c2dce9`），可以跑 | 等 AO 的實際花費確定後再決定；累計不能超過 USD 89 |
| F5 [#659](https://github.com/Polalalabear/amidst/issues/659) 論文 | 論文 md → PDF | E3 章節已合併（#693，`docs/paper/F5_PAPER_DRAFT.md`） | E5 章節等結果；#659 仍是 `blocked` |
| E4 | 探索性附錄 | 暫停（D356）。`claude/feat-e4` `f8f21afa` 保留 | — |

### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| Codex PR [#690](https://github.com/Polalalabear/amidst/pull/690)（Draft）：#676 顏色修正、#677 的四個後端欄位、三個小修正 | 審查 APPROVE（E5 後合併） | 會改變 B1 快照的來源雜湊（`scripts/evaluation/e3_cases/baseline.py:55-59`），**E5 結束前不能合併**。合併後 #676 不能關閉：主因可能是 gate 4 m／growth 0，要等 #589／R2 |
| [#675](https://github.com/Polalalabear/amidst/issues/675) LIVE 開放 Agent 決策（Codex） | 啟動和開關已驗證 | 資料外傳暫停到 E5 結束（D359） |
| [#677](https://github.com/Polalalabear/amidst/issues/677) LIVE UI/UX | 已合併（#695 `ada45f31`），issue 已關閉 | 還沒部署到 8791。後續：#690 合併後，前端改讀 `gate_m_effective`／`reject_reason`／`cand_id` |
| [#672](https://github.com/Polalalabear/amidst/issues/672) LIVE 追其他目標 | 設計在假設文件 §0.2 | 排在 E5 之後 |
| [#633](https://github.com/Polalalabear/amidst/issues/633) LIVE 改 workbench-v2 風格 | — | 11-25 之後 |

### 3.3 研究紀錄、報告與發表

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 海報與簡報 | 已完成。使用者選了架構圖 ③ components。交付資料夾見 §5 | 結果數字等 E5；pptx 還沒在 PowerPoint 或 Keynote 開過 |
| open-slide 原始專案 | 在 `local/evidence/presentation-pack-20261123/slides/open-slide/`（資料夾，SHA-256 不適用） | `node_modules` 約 269 MB，不再需要時可以刪（使用者執行） |
| [#479](https://github.com/Polalalabear/amidst/issues/479) 報告素材、[#674](https://github.com/Polalalabear/amidst/issues/674) 更新紀錄 | 持續追加 | — |

### 3.4 8785 demo

- 8785 的 pin 還在 `c988ed60`（使用者 2026-11-23 核准；gate `local/evidence/gate-pin-20261123/RESULT.txt`，SHA-256 `1f13c82beb36704e7ca653dd0b7041887ce290b2a17f93134654dea9496b92d2`）。
- main 已經前進到 `ada45f31`。要換 pin 就跑 gate，再請使用者核准，不能自己改。

### 3.5 Codex 的任務

- 目前沒有可以做的工作，等 E5 結束；之後第一件事是合併 #690，再做 #675。
- [#623](https://github.com/Polalalabear/amidst/pull/623)、[#612](https://github.com/Polalalabear/amidst/issues/612)、[#594](https://github.com/Polalalabear/amidst/issues/594)：11-25 之後。
- [#589](https://github.com/Polalalabear/amidst/issues/589)、[#574](https://github.com/Polalalabear/amidst/issues/574)、[#566](https://github.com/Polalalabear/amidst/issues/566)：被擋住（#566 目前沒有 `blocked` 標籤）。

### 3.6 流程與整理

| 工作 | 卡在哪裡 |
| --- | --- |
| PROGRESS 補列 #656–#696、CODE_DOC_MAP | 大更新，之後再做 |
| `real-e2e.mjs` 多畫面格數 | 未排定 |

## 4. 新協調者的第一件事

1. 等 E5 AO 子 session（`local_073d1ce8-8722-42b4-b1c2-1d65cdac1305`） 回報，看報告 PR，派 Sonnet medium 審查；評分程式（complex code 邊界）有疑慮就交給 Opus。通過且 CI 綠就合併，在 #93 記 D362，在 #674 追加一則。
2. 依 AO 的實際花費決定要不要跑 AO-L（累計 ≤ USD 89）。
3. E5 結束後：合併 #690，請 Codex 做 #675；論文補 E5 章節，海報和簡報填入數字；8785 換 pin 要經過 gate，並由使用者核准。

## 5. LOCAL 產物

`local/evidence/presentation-pack-20261123/deliverable/`：約 8.9 MB，18 個檔案；各檔 SHA-256 在 `deliverable/README.md`（該 README 的 SHA-256 `9e731177cc361aa765910410b2d402a1aea90a63fb67b9fadbaadc9e322e8f55`）。可以用 `local/evidence/presentation-pack-20261123/scripts/` 重建。

| 項目 | 內容 |
| --- | --- |
| `slides/amidst_slides.pptx`、`slides/amidst_slides.pdf` | 可編輯簡報（python-pptx 原生物件）和 PDF |
| `poster/poster_A1_academic.pptx`、`poster/poster_preview_quicklook.png` | 海報和預覽 |
| `images/` | 12 張圖：架構圖 ③ components、決策流程圖、五張決策點圖、兩張八鏡頭畫面、鏡頭覆蓋圖、兩張工作台截圖 |
| `README.md` | 檔案清單與 SHA-256 |

上一層 `local/evidence/presentation-pack-20261123/`（資料夾，SHA-256 不適用）另有 `images/`、`poster/`、`scripts/`、`slides/`（含 open-slide 專案）。決策點圖和場景圖的來源是 `local/evidence/e3-figures-20261123/`（#670）。
