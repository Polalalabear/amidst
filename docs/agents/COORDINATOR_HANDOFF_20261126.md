# 協調者交接 2026-11-26

接在 [20261124b](COORDINATOR_HANDOFF_20261124b.md) 之後。**之後的狀態以 #93（工作清單與 D 決策）、#674（更新紀錄）和各 PR 為準**。新的協調者全程用繁體中文回覆（D255）。審查由另一個對話接手。

## 0. 版本與環境

- `main` = `10a1384c`（#715、#716 已合併）。下一個決策號 **D382**。
- 8785 pin `c988ed60`（`local/demo-pin.json`，2026-11-23 核准），8785 沒在聽。8791（PID 45196，舊版 LIVE）、8795、8796 在聽，都沒動。
- 磁碟約 10 GiB。第三個寫入者開工前要 ≥ 9 GiB，程式保護 8 GiB，剩 5 GiB 停。
- 費用：使用者讀 API platform 的 **USD 38.17**（D375，`local/evidence/api-usage/RECONCILIATION_20261124.json`，SHA-256 `a1bb6e9dabb1bce1eebef8934a294dec4c196a12c2722b93752aa86fb43c4635`）＋之後新帳本列；上限 90。之後沒有新的付費呼叫。

## 1. 本段決策（D376–D381，原文在 #93）

| D | 內容 |
| --- | --- |
| D376 | 工作全開給 Codex 與 Neon（原 Argon），Claude 只審查 |
| D377 | E6 方向：P1 去錨定對原 AO、P2 選定 Agent 組對 **B1**（Holm 校正，四元件取最大 p）；R-N（規則決策＋中性追蹤器）為機制與次要；3 段診斷和 12 段正式資料嚴格分離；**審查分四批**，每批 Codex、Neon 互審後一次送審 |
| D378 | Argon 改名 **Neon**；標籤 `owner:neon`；舊分支與紀錄不改寫 |
| D379 | 移機順序：第 1 批審查 → 盤點要搬的檔案（含 12 份 `.blend`，只列不刪）→ 核對可攜性 → 搬移驗證 → 才做 laya／本地模型。搬完後 Neon 可讀寫本機，和 Claude、Codex 同等級 |
| D380 | 媒介：使用者的雲端硬碟，只當私人搬移（不分享）；Claude Code 仍是最終審查者，像開源維護者一樣**從 GitHub 讀 PR／issue／決定**來審 |
| D381 | gate 標準 B：被採用的 Agent 回答全部有一字不差收據即 PASS；因 `PROVIDER_UNAVAILABLE` 沒收據的要明確退回規則並寫成記錄行（`... PASS`，不寫 FAIL） |

## 2. 工作（依類型；預計產出／目前進度／卡住）

### WP5 與 Agent 決策（E6、E7）

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #717 → PR #723（Codex） | 16 段答案表、錯誤歸因、AO 描述性拆解、R-N | head `30563f0f`，CI 綠，Neon APPROVE（只審 GitHub，LOCAL 數字未重現） | 等 Claude 第 1 批審查；**PR 寫的輸出資料夾 `local/evidence/cx-e6-717-20261124/` 在 Mac 上找不到（SHA 不適用：資料夾不存在）**，審查時要 Codex 補或說明 |
| #718 → PR #726（Neon） | E6 預登草稿、12 段劇本規格、資料分離自動檢查 | head `9e6c54b6`，CI 綠；Codex 兩輪 NEEDS_CHANGES 後已修 | **等 Codex 第三輪複審**，之後進第 1 批 |
| #721（Codex） | 去錨定／歷史／摘要實作與 3 段診斷 | blocked | 等 #718 合併、付費與外傳影格同意（第 2 批） |
| #727 E7（新） | 本地決策器（Qwen-VL 類、laya）延遲與決策探索 | blocked-user | 等 #598 移機完成 |
| #684 E5 | — | 已判定（H8a、H8b、H8d 不成立，H8c 無法判斷）；事後檢查在留言 | 只剩收尾，可在 E6 後關 |

### 研究紀錄與報告

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #719 → PR #724（Neon） | 論文收尾、中英文 README（E3／E5） | head `32218a1a`，CI 綠，Codex APPROVE | 等 Claude 審查；**期限 11-25 已過**，可先審先合 |
| #659 F5 論文 | 交付資料夾定稿 | 進行中 | 依 #724 合併後收 |
| #722（協調者） | E6 計畫、交接、索引、進度導覽到 #722、本交接 | head 見 PR，CI 綠 | 第 1 批審查 |

### 8785 demo

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #720 → PR #725（Codex） | 零付費檢查、20 題 Q1–Q3 功能驗收（14/20） | head `d8ebdeb1`，CI 綠，Neon APPROVE | 等 Claude 審查；**輸出資料夾 `cx-demo-720-20261124/` 在 Mac 上找不到**；截圖與實跑未驗證 |
| #710 → PR #714（Codex） | 新版前台接上 3D 與 display_estimate | head `e008d715`，CI 綠，程式層 APPROVE | 截圖要先給使用者看（URL、服務種類）；#714 截圖在 `local/evidence/screenshots-714-20261124/`（MANIFEST SHA-256 `24a38dfcdec6893f7bba6b4efa87c67e8bb91d302166e4bef2c2ce4e15b61560`），README 由 #720 補 |
| #700 換 pin gate | 依 D381 標準 B 判定 | r3b（`edb642c6`）依新標準證據足夠，只當參考 | 第 1 批合併後定目標 commit，**在新 commit 重跑 gate**；換 pin 由使用者核准 |

### 流程與整理

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #598 Windows 移機 | 檔案盤點、可攜性核對、快照 S1、Windows 兩遍一致 | blocked-user，計畫在 issue 本文 | 等第 1 批合併 |
| 快照 S1 規則（建議，未寫進 #598） | Windows 唯讀快照；`AMIDST_ARTIFACTS`、`AMIDST_API_USAGE_DIR` 指到快照外；`demo-owned-v1/state/` 不搬（`state_root` 沒有環境變數可改）；要改就在 Mac 走 PR 再發 S2 | 已向使用者說明 | 使用者尚未確認是否寫進 #598 |
| 跨平台風險 | — | 已查 | repo 沒有 `.gitattributes`（Windows CRLF 會改 SHA）；3 個 git 符號連結（`docs/DEVELOPMENT_RULES.md` 等）；`local/` 最長路徑 205 字元。S1 前要處理 |
| 暫停到 11-25 後的項目 | — | 仍暫停 | #681、#675（`blocked-user`）、#589、#574、#566、#633、#672、#630；使用者還沒說要恢復 |

### 即時模式

全部暫停（見上一列）。8791 仍是舊版，未部署 #703。

### Codex 與 Neon 的任務

- Codex：#723、#725 等審查；#726 第三輪複審進行中；補兩個缺少的 LOCAL 輸出資料夾。
- Neon：#724、#726 等審查。搬完前 Neon 只用 GitHub。

## 3. 審查交接（給審查對話）

- **第 1 批**：#722、#723、#724、#725、#726（等 Codex 第三輪 APPROVE），#714 可同批。依 D377，批內一次送審；依 D305，審查通過＋CI 綠就用 merge commit 合併並刪分支，但 **UI 先給使用者看截圖**、**換 pin 要問**。
- 審查方式（D380）：從 GitHub 讀 diff、跑 focused tests；PR 要附可重跑指令、彙總數字與 LOCAL SHA-256。抽查 LOCAL 時一次只取單一檔案。Neon 的 APPROVE 不含 LOCAL 數字重現。
- 合併後依序：定 pin 目標 commit → Codex 重跑 gate（標準 B）→ 使用者核准換 pin → #598 盤點與 S1。

## 4. 待使用者決定

1. 快照 S1 規則是否寫進 #598。
2. 第 1 批合併後，8785 要釘哪個 commit（是否含 #714）。
3. 第 2 批的付費與外傳影格（#721）。
4. E7 是否微調（要用 GT 當標籤，牽涉 GT 隔離）；下載權重需同意。
5. 暫停項目何時恢復；#676、#589 §4.5。

## 5. 第一件事

讀 #93 最新 D376–D381 與本文 §2，確認 #726 的 Codex 第三輪結果；等使用者說開始，就照 §3 審第 1 批。
