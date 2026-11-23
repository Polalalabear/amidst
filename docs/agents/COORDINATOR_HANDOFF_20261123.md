# 協調者交接（2026-11-23）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> 依據：更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 至第 18 則；`main` @ `c988ed607cb2941bde2b84688f9675213efd2a98`。本文件是快照；現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（D 號，下一個是 **D356**），所有更新追加在 #674（append-only）。上一份交接是 `docs/agents/COORDINATOR_HANDOFF_20261122.md`。

## 1. 一句話現況

E3 跑完了：在 16 段困難劇本上，**這個整合下的看圖 Agent 沒有勝過規則**。H1、H2、H4 判「不成立」，Sonnet 和 Opus 都確認不是程式錯誤（D354）。使用者決定先做 **E4：條件式 Agent 覆寫**（探索性改良），再寫 F5 論文（D355）。期限 2026-11-25。

## 2. 目前狀態

| 項目 | 狀態 |
| --- | --- |
| main | `c988ed60`（#671 合併） |
| 8785 demo | pin `c988ed60`（2026-11-23 使用者核准，gate `local/evidence/gate-pin-20261123/RESULT.txt` 15 項 PASS）。PID 23134，終端 tab 1。http://127.0.0.1:8785/workbench-v2/ |
| 8791 LIVE | `local/runtime/live-main` @ `c988ed60`，PID 22779，終端 tab 0。http://127.0.0.1:8791/ |
| 磁碟 | 約 11 GiB 可用（第三個寫入 session 前需要 ≥ 9 GiB；剩 5 GiB 就停；8785 在 < 8 GiB 時不啟動） |
| 花費 | 交接前累計 USD 22.4＋F3 0.33＋F4 27.28＋8785 gate 0.13 ≈ **USD 50**。上限 USD 100，累計到 90 前不用問（D344）。E4 預估 +15–20 |
| E3 分數 | 已評分並判定（#678）。凍結評分器 `src/amidst/evaluation/e3_scoring.py` SHA-256 `acacce39…7d08` |

## 3. 所有工作（依類型）

### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [F1 #660](https://github.com/Polalalabear/amidst/issues/660) 評分器＋預先登記 | — | ✅ #662 `ea0db4fd`；修訂 #667 `744f9d7f`（D348、D349）、#671 `c988ed60`（D350 H2 補充診斷、A3 §7） | — |
| [F2 #656](https://github.com/Polalalabear/amidst/issues/656) 空間圖 | — | ✅ #664 `8af69ea4`。E3 前閘門：LIVE 8 台都沒通過，E3 不裁牆（D348） | — |
| [F3 #657](https://github.com/Polalalabear/amidst/issues/657) H6 Agent 接管 | — | ✅ #666 `61867089`（M1：答案無法採用→交回規則；M2 schema；M3 場景上下文失敗不靜默） | 8CAM／B-05 未接 → Codex #679 |
| [F4 #658](https://github.com/Polalalabear/amidst/issues/658) E3 實驗 | 報告 `docs/operations/F4_E3_REPORT_658.md` | **PR [#678](https://github.com/Polalalabear/amidst/pull/678) head `b4e6a07f`，CI 綠**。Sonnet 正式審查 PASS；Opus 裁決負面結果成立；M1–M5 文字已補 | **Sonnet 複審 M1–M5 中**（session `local_02bd80a4…`）。PASS 就依 D305 合併（不刪 `claude/feat-e3-run` 之前先確認工作線不再用） |
| **E4（D355）** 條件式 Agent 覆寫 | `E4_PREREGISTRATION_20261123.md`（跑前寫死）、實作（只改 Agent 路徑）、A2-E4 K=3 × 16 段、`E4_REPORT`；探索性 | 已交給工作線（分支 `claude/feat-e4`，要開 issue＋PR） | 等 #678 合併後開工 |
| [F5 #659](https://github.com/Polalalabear/amidst/issues/659) 論文與交付資料夾 | 論文 md（唯一正本，進 git）→ PDF；研究更新稿進 `docs/operations/`；加 E4 探索性一節 | 未開始 | 等 E4。依 D355 可平行先寫 E3 章節（檔案不重疊時） |
| #623 預錄 est_xy／8CAM | — | 暫緩（D344） | 11-25 之後 |

**E3 結果（#678，預先登記 §6）**

| 假設 | 判定 | 數字 |
| --- | --- | --- |
| H1 | 不成立 | A2 − B1 錯人秒 +129.8 s [36.2, 218.5]；McNemar p = 0.648 |
| H1 次要（A3） | 探索性 | +4.3 s [−12.4, 23.6]（9 段／38 點；77/156 答案過期） |
| H2 | 不成立 | A1 − B1 +145.1 s；A2 − B2 +129.8 s（B2 追蹤＝B1） |
| H4 | 不成立 | A2 top-1 3/111；**102/111 點沒有排名**，有排名時 3/9；hint 只跟著 NOT_VISIBLE（62/1684） |
| H5 | 本次未判定 | 證據仍只有 W1 |
| H3 | 描述性（D353） | override 被採用 155 次，第一個 tick CORRECT 62（40%） |

**失敗機制（Opus）**：34% 被採用的 SELECT 落在看不到目標的鏡頭；AMBIGUOUS 時選錯人，且 LIVE 路徑每次採用都重設追蹤器（C3／C4／C6 的錯誤 75–79% 發生在規則正確的 tick）。可能歸給程式的上限 73.4 s 全扣掉，A2 仍比 B1 多約 56 s。**論文措辭**：範圍限「這個整合」；與 W1 對照（目標在畫面時辨識較好，F1 0.887 vs 0.518）；差距在「判斷不在」與「怎麼接進追蹤器」。不能寫「看圖 Agent 普遍比規則差」。

**E4 設計（D355）**：可信追蹤鎖定（規則穩定時 Agent 只提候選、不重設）＋條件式覆寫（失聯或可信度下降才採用，採用前驗證鏡頭／框／外觀／時間戳）＋短期追蹤記憶（有時限）＋ NOT_VISIBLE／UNCERTAIN／下一鏡頭排序分開（每次都給排序）＋執行紀錄補 `detection_id`、候選清單、請求原文。假設 H7a（錯人秒低於 E3 A2，對 B1 不差）、H7b（盲區誤鎖降）、H7c（有排名點增加）。B1／B2 沿用；同評分器、同 16 段；標探索性（看過 E3 後在同一批劇本上的改良）。

### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| [#672](https://github.com/Polalalabear/amidst/issues/672) LIVE 追其他目標（探索性） | 設計在假設文件 §0.2（#673 `2f5e5a9f`） | E3 已凍結，但會改 `advisor.py`／`scheduler.py`，和 E4 重疊 → E4 之後 |
| #633 LIVE 改 workbench-v2 風格第二段 | — | 11-25 之後 |
| #588／#589／#574 relock 門檻、R2 接線、A/B 整合 | blocked | 等 relock 門檻量測 |

### 3.3 研究紀錄與報告

| 工作 | 狀態 |
| --- | --- |
| 版本管理（D351） | 正本只在 main；論文以 md 為唯一正本，PDF 由 md 產生；Claude Docs 稿（`B7oycBdnYfkeK1U1JiPWSL`）不再手改；衍生文件標「依據 #674 至第 N 則／main @SHA」；E3／E4 判定進 main 後一次重產 |
| 研究更新稿 `local/evidence/research-update-20261122/RESEARCH_UPDATE_20261122.md` | 已標「已過時」，保留為歷史快照 |
| 論文 `local/evidence/final-package-20261120/report/amidst_paper_20261120.{md,pdf}` | 仍是 W2 前的數字 → F5 |
| 引用索引待更新清單 | #674 第 17 則（CODE_DOC_MAP、PROGRESS、假設文件 §0、論文、交付資料夾 README／MANIFEST、#479） |
| 外部審查回饋（D350） | 已採用 |

### 3.4 8785 demo

| 工作 | 狀態 |
| --- | --- |
| pin 更新 | ✅ `c988ed60` |
| `real-e2e.mjs` 多畫面格數 | 仍斷言 F3 前的格數；gate 用本機補丁 `local/evidence/gate-pin-20261123/real-e2e-local-patch.diff`。已交給工作線，併進下一個 PR |
| 3D 按鈕、8791 透視預設關 | gate 沒驗（只有單元測試） |

### 3.5 流程與整理

| 工作 | 狀態 |
| --- | --- |
| 更新測試文件 | **使用者確認整體更新無誤後的第一件事**（2026-11-20 指示），尚未開始 |
| `Q1Q5_PROGRESS.md` | 只到 #655；補列 #656–#680，來源用 #674 |
| D319 第二輪檢索 | 三天計畫之後 |

### 3.6 Codex（可以平行多項，檔案不和 E4 重疊）

| 工作 | 產出 | 狀態 |
| --- | --- | --- |
| [#668](https://github.com/Polalalabear/amidst/issues/668) E3 論文素材（PR [#670](https://github.com/Polalalabear/amidst/pull/670) `d57b5319`） | 16 張前後拼圖、8 張決策地圖、八鏡頭總覽 | Sonnet NEEDS_CHANGES：只差圖說加「僅為示意；E3 推論未使用牆面裁切（D348）」。修好後交 Sonnet 複審 |
| [#679](https://github.com/Polalalabear/amidst/issues/679) CX-H6 8CAM／B-05 接 Agent＋手動改選 | Draft PR `codex/feat-h6-8cam`＋截圖 | ready，可以現在開工 |
| [#680](https://github.com/Polalalabear/amidst/issues/680) CX-F4R F4 主結果獨立重算 | `docs/evaluation/F4_INDEPENDENT_RECOMPUTE_20261123.md` | ready，可以現在開工 |
| #652 E3 困難劇本 | ✅ #663 `adb69449`、#665 `644ae036`（16 段、68 點、33 個 H4 點） | 可以關 issue |
| #623 | 暫緩 | — |

## 4. 決策 D345–D355 摘要（下一個是 D356）

- **D345** Claude 單一工作線（F1→F4）；使用者實測三問題併入 F2／F3。
- **D346** 靜態牆與門可以進 `scene_context`（只限 `occluders_full_height`、`door_openings`，附 SHA）。
- **D347** 接受統一評分新尺；門檻寫成 `verdict_*`；樣本門檻不降；看到 E3 資料後 §4／§6 凍結。
- **D348** F2 閘門維持嚴格：E3 的 LIVE 不裁牆；H4 的空間資訊不含牆面裁切。
- **D349** #665 的 7 段納入 E3；兩批一起評分。
- **D350** 外部審查回饋：收斂到 E3；H2 補充診斷；GT 代理框抽查；F4 報告逐段。
- **D351** 報告版本管理：一個正本，衍生唯讀；論文 md 為唯一正本。
- **D352** F4 預算上限設定錯誤的重跑規則（只依 `CALL_BUDGET_EXHAUSTED` 欄位、同組 K 次全部重跑）。
- **D353** H3 只做描述（探索性）；H6 用完成度表；#666、#673 合併。
- **D354** F4 負面結果接受；報告補 M1–M5 後合併；接 F5。
- **D355** E4 採用；先 E4 再 F5；D344 的「一次一個大 feature」是避免處理零碎小問題，**不是禁止平行**。

## 5. 進行中的 session

| session | 角色 | 狀態 |
| --- | --- | --- |
| `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`（F1 工作線） | Claude 工作線：F4 收尾 → E4 → F5 | 已收到 D355 的 E4 brief |
| `local_02bd80a4-e456-4919-93cb-8d82f3c681ff`（Sonnet 審查） | 所有 PR 的正式審查 | 正在複審 #678 M1–M5；#670 等 Codex 修完再審 |
| `local_364c082e-2607-49f5-88f3-671219bb10a2`（Opus） | complex code／決策裁決（做過 #662、#664、#666、#678） | 閒置，可用 SendMessage 續用 |
| `local_3b5c01e6-8e1b-416b-968b-9c480439816d`（pin gate） | 8785 gate | 已完成，可封存 |

## 6. 流程規則重點

- 協調者只規劃、決策、寫 brief、合併。後續指示用 SendMessage 送給已有脈絡的 session。
- 審查：每個程式 PR 由 Sonnet 正式審查；complex code 或決策點交 Opus，只看被標出的點。審過且 CI 綠就用 merge commit 合併（D305）；UI 和 pin 先給使用者看截圖。
- `~/amidst` 是 8785 pin 資料夾：不改檔、不切分支、不 commit。寫檔一律在 scratchpad 精簡 clone。
- 合併、kill、approve 被權限擋下時，給使用者一條指令自己跑（每條只給一次）。
- 付費呼叫一律經 ApiGuard；每個行程用自己的帳本；到 USD 90 前不用問。
- Blender 渲染免問，但要回填 issue 和 PR。
- 每個節點都要在 #674 追加一則（格式見 #674 本文）；決策正文寫在 #93。
- 被 session 事件喚醒的回合不能開新 session，改用提案卡或 SendMessage。

## 7. 新協調者第一件事

1. 讀本文件、[#674](https://github.com/Polalalabear/amidst/issues/674) 最後幾則、#93 的 D354、D355。
2. 等 Sonnet 複審 #678 M1–M5：PASS 且 CI 綠就合併，然後通知工作線開始 E4。
3. 把 Codex 的三個任務交給使用者貼上：#670 圖說修正、#679、#680（派工文字見交接訊息）。
4. E4 預先登記開出 PR 時，先審門檻（Opus），再讓工作線開跑。
5. 使用者確認整體無誤後，第一件事是更新測試文件。
