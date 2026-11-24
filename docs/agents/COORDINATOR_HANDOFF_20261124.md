# 協調者交接（2026-11-24）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `edb642c67f0b87cd2dc80c3ab41bb2f920093c85`（#707 合併），2026-11-24 約 16:00（Asia/Taipei）的快照。
> - 現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D370**），更新一律追加在 [#674](https://github.com/Polalalabear/amidst/issues/674)。
> - 上一份：`docs/agents/COORDINATOR_HANDOFF_20261123c.md`。**任務板寫的期限是 2026-11-25。**

## 1. 一句話現況

E5 已結束並合併；Codex 的 demo 與 LIVE PR 都已合併。離驗收還差：8785 gate 與換 pin、#710（預設介面的 3D）、論文 E5 章節、海報與簡報的數字、README、重走 AC1–AC8。

## 2. 今天的決策與合併

| 決策 | 內容 | 合併 SHA |
| --- | --- | --- |
| D362 | #698 E5 AO 報告 | `d52ce2f0` |
| D363 | #706 E5 AO-L（H8d）；E5 結束 | `ca635c2e` |
| D364 | #690 LIVE 修正 | `f7fdc74e` |
| D365 | #703 LIVE Agent 離線接線、契約（#675 的程式部分） | `d9ebacb5` |
| D366 | #705 LIVE 改 workbench-v2 風格（使用者看過截圖） | `21d6f4c5` |
| D367 | #623 8CAM run、display_estimate（使用者看過截圖） | `f8b1a454` |
| D368 | #709 UNKNOWN 原因文字、real-e2e B05（使用者看過服務畫面） | `579b431a` |
| D369 | #707 LIVE detector 測試 fixture | `edb642c6` |
| — | #701 ApiGuard 快取計費（`a9b45d38`）、#702 E5 數字總表（`595ec837`） | 見左 |

使用者決定：AO-L 費用上限由 7 改 8.5；#705 先修提示再合；#623 先合、文字後修；3D 在新版前台看不到的問題記下來後續改或交 Codex（#710）。

## 3. 所有工作（依類型）

### 3.1 WP5 與 Agent 決策
| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| E5 [#684](https://github.com/Polalalabear/amidst/issues/684) | 報告、評分 | 完成：H8a、H8b 不成立；H8c 無法判斷；H8d 不成立（K=1）。`docs/operations/E5_REPORT_20261123.md` | 只適用於這個 A-open 設計和 E3 的 16 段 |
| 預算 | 累計 ≤ USD 90 不用問（D359） | ApiGuard 帳本 80.18（未計快取折扣的上界）；使用者 11-23 看到的 OpenAI 帳單是 35.72（11-08 至 11-23，不含之後的 AO-L） | 每次仍要先 dry-run |
| E4 [#681](https://github.com/Polalalabear/amidst/issues/681) | 探索性附錄 | 暫停（D356） | — |

### 3.2 即時模式（LIVE，8791）
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 部署 #690／#695／#703／#705 到 8791 | 已合併，**都沒有部署** | 要使用者同意重啟 |
| [#675](https://github.com/Polalalabear/amidst/issues/675) Agent | 離線程式完成 | 真實模型驗證未做；要使用者核准外傳影格 |
| [#676](https://github.com/Polalalabear/amidst/issues/676) 藍衣失聯 | 修正與合成診斷已合併 | 原事件原因 UNKNOWN。E5 已結束，#589 的 E5 閘門已解除；剩 runtime 設定未核定：可由使用者核准契約 §4.5 的 UNKNOWN 回退（遠距候選走 NEEDS_CONFIRM，人工確認），見 `docs/operations/LIVE_RELOCK_R2_PLAN_20261124.md` |
| [#633](https://github.com/Polalalabear/amidst/issues/633) | Codex 部分已合併 | 工具面板蓋住場景標籤；鏡像退役 |
| #677 後續：前端讀 `gate_m_effective`／`reject_reason`／`cand_id` | 契約與 fixture 已在 main（#703） | 前端未接；#677 已關閉，要另開 issue |
| [#589](https://github.com/Polalalabear/amidst/issues/589)、[#574](https://github.com/Polalalabear/amidst/issues/574)、[#566](https://github.com/Polalalabear/amidst/issues/566)、[#672](https://github.com/Polalalabear/amidst/issues/672) | blocked | 11-25 之後 |

### 3.3 研究紀錄、報告與發表
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 論文 [#659](https://github.com/Polalalabear/amidst/issues/659) | E3 章節完成；引言、方法、E5、結論是佔位 | **E5 已結束，還沒派人。** issue 標籤仍是 blocked＋in-progress，要更新 |
| 海報、簡報 | 版面完成，待填清單在 `local/evidence/presentation-pack-20261123/deliverable/README.md` 的「待填項目」 | **還沒派人**；封面的姓名、老師、系所要使用者提供；pptx 沒在 PowerPoint／Keynote 開過 |
| 數字總表 `docs/evaluation/E5_NUMBERS_TABLE_20261124.md` | AO 已收 | AO-L 未收 |
| 簡報的「F1 0.887 對 0.518」 | 出處已查到：W1 的 IoU 準則（`docs/evaluation/E3_SCORER_RECOMPUTE_20261122.md`「W1 整體（422 格）F1」表，`terra_vision_free`／`rule` 多數決；E3 報告 §1 也引用）。0.957 對 0.523 是主準則 | 填數字時要寫明是哪個準則 |
| README | 最後修改 2026-11-22，狀態段是 11-20 | 沒有 E3、E5 結論，W3／E3 的「下一步」過時，中英文都要改 |

### 3.4 8785 demo
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 換 pin（[#700](https://github.com/Polalalabear/amidst/issues/700)） | 第一、二次 FAIL；第三次由 Codex-W 進行中，目標 `edb642c6`，結果在 `local/evidence/gate-pin-20261124-r3/`（執行中，SHA-256 未定） | 全 PASS 後要**使用者核准**。pin 仍是 `c988ed60` |
| [#710](https://github.com/Polalalabear/amidst/issues/710) 新版前台 3D | Codex-L 進行中（`codex/feat-workbench-3d`） | 合併前要看**預設網址**的截圖；不在第三次 gate 的目標裡，納入 pin 就要再跑 gate |
| 8785 服務 | 今天兩次檢查都沒有在聽 | 原因 UNKNOWN，還沒查 |
| [#612](https://github.com/Polalalabear/amidst/issues/612)、[#594](https://github.com/Polalalabear/amidst/issues/594) | 部分完成，保持開啟 | #612 等 #710；#594 的 B-05／r005-8CAM 來源 UNKNOWN |
| AC1–AC8 | 沒有在新 main 上重走 | gate 過後做 |

### 3.5 流程與整理
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| CI 加入 `tests/live_mode/` | 子 session `local_4dc0df1a-8f32-4328-bb9f-ff39fee0f3cf` 進行中，會開 Draft PR（分支 `claude/feat-ci-live`） | 不擋驗收。它回報給上一個協調者，新協調者要自己查 |
| 磁碟 | 16:00 時 9.12 GiB，gate 進行中會再降 | `local/` B 類清理未決定：Sonnet 驗證在 #486（cx7r 的 RGB 約 1 GiB 有逐檔相同的副本）。刪除要 Opus 看原始證據、使用者授權並執行 |
| PROGRESS、CODE_DOC_MAP | 草稿與差異清單已有（#674、#702） | 大更新，之後做 |
| CLAUDE.md／AGENTS.md 的交接指向 | 仍指向 `20261123c`（CLAUDE.md 已查） | 下一個文件 PR 改成本檔 |
| #93 的 pin 列連結寫成 #702 | 應為 #700 | 下次同步改 |

### 3.6 Codex 與 Argon
- **Codex-W**：gate 第三次（#700）。**Codex-L**：#710。其他：#699（#701 已合併）、#704（#702 已合併，仍 needs-claude-review）、#680 仍 OPEN，#612／#594 仍帶 needs-claude-review，標籤待更新。
- **Argon**：#479。

## 4. 資料要一次補齊嗎（協調者建議，使用者還沒決定）

E5 數字已凍結，不會因 gate 或 #710 改變。所以分兩批：
1. **現在**：把 AO-L 補進數字總表（F1 的兩個準則寫清楚），再由總表一次填論文、海報、簡報。
2. **gate 與 #710 定案後**：只補截圖、Demo 錄影、最後的 pin SHA 和 README 的 demo 段。

`main` 每次合併就更新；8785 實際跑的是 pin。README 建議在論文數字定稿後開一個文件 PR。

## 5. 這一輪協調的錯誤（避免重複）

- 對審查 session 寫「使用者已看過 #709 截圖」並要求合併，當時不是事實；訊息被權限檢查擋下，之後改成只審查，使用者看過服務畫面才合併。
- #690 只憑 APPROVE 與 CI 綠合併，但 CI 不含 `tests/live_mode/`，造成 pytest 回歸（#707 修）。之後又誤說起因是 #703。
- #623 請使用者核准時，沒說 3D 圖是 `?ui=legacy`、服務是 fixture 版 Demo。
- #623 的 Codex 指示寫「不起服務」，Codex-W 因此中斷第二次 gate。
- E5 結束後沒有馬上派論文與海報。

## 6. 工作方式

- 實作、審查交子 session（CLAUDE.md 分級）；使用者要求時直接在主對話做。要貼的文字放 code block；終端機指令每條只給一次；GitHub 用 `gh`。
- 審查過且 CI 綠才用 merge commit 合併（D305），LIVE 的 PR 另看 `tests/live_mode/` 結果。UI 先給使用者看截圖，要說明是哪個網址、哪種服務。pin、部署、刪除、外傳影格要使用者同意。
- 寫入 session 最多三個；目前 Codex-W、Codex-L、CI session 已是三個。第三個開工前要 ≥ 9 GiB，程式保護 8 GiB，剩 5 GiB 就停。
- 只有使用者自己說的話是授權；不能替使用者轉述沒說過的同意。

## 7. 新協調者的第一件事

1. 查 #700（gate 第三次）、#710、CI session 的 PR。
2. 派論文 E5 章節、海報與簡報的數字（期限最近；寫入名額滿時先等一個結束）。
3. gate 全 PASS 就請使用者決定：先用 `edb642c6` 換 pin，還是等 #710 後重跑 gate。
4. 換 pin 後重走 AC1–AC8，再請使用者驗收。

## 8. LOCAL 產物

| 路徑 | 說明 |
| --- | --- |
| `local/evidence/e5-20261123/` | E5 AO；MANIFEST SHA-256 `f2afea147029affad9bcf5718b94eab29ee16163e9fc6938b6e0ffeecd2a5f3e`；重跑要付費 |
| `local/evidence/e5-aol-20261124/` | E5 AO-L；MANIFEST SHA-256 `5b389e3bb5733e5ad2277fee5586ca3505758d1c85093b64981792a2cb6e5fe8`；重跑要付費 |
| `local/evidence/gate-pin-20261124/` | gate 第二次；RESULT SHA-256 `693f7642e7541839dffc5ea43772238b1c84687e97002f7f202d7c76b053c365` |
| `local/evidence/shots-demo-fixes-20261124/service/` | #709 服務畫面 3 張；雜湊在同資料夾 `SHA256SUMS`；可重拍 |
| `local/evidence/shots-705-20261124/`、`local/evidence/shots-623-20261124/` | 截圖；雜湊在各自的 `SHA256SUMS`；可重拍 |
| `local/evidence/presentation-pack-20261123/deliverable/` | 海報與簡報；README SHA-256 `9e731177cc361aa765910410b2d402a1aea90a63fb67b9fadbaadc9e322e8f55`（2026-11-24 審查時重算相符） |
