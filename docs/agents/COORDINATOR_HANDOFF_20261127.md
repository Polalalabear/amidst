# 協調者交接（2026-11-27）

快照時間 2026-11-27 約 08:40（+08:00）。main = `a90a7884`；8785 pin = `5727fc9a`；下一個決策號 **D399**。之後的狀態以 [#93](https://github.com/Polalalabear/amidst/issues/93)、[#674](https://github.com/Polalalabear/amidst/issues/674) 為準。新的協調對話**全程用繁體中文**（D255）。

## 0. 先讀

1. 本文件。
2. #93 本文第 00 節，以及 D388–D398 留言。
3. #674 最新幾則。
4. 規則：`CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`。

## 1. 角色與規則（本段新增）

- **D389**：審查通過＋CI 綠，就由 Claude 用 merge commit 合併並刪分支。`--match-head-commit` 一定要用 `gh pr view --json headRefOid` 查到的完整 SHA。
- **D391／D396**：Codex 額度不足時由 Claude 代做，包括 E6 錄製。E6 是 LIVE WebGL 無頭錄製，不是 Blender 渲染。#732 的前提 G1–G5 全部由 Claude 做。
- **D395**：刪除和嚴重到需要使用者看的事以外，指令由 Claude 直接執行，包括快轉 `~/amidst`、以已審過的 gate 執行 `demo_pin.py approve`、重啟 8785／8791、合併。8785 的啟動指令是 `cd ~/amidst && ./start_445_demo.command --port 8785`。
- **D397**：費用累計 USD 38.17＋新帳本列，不超過 90 就不用問。每次先做 ApiGuard dry-run 並記帳。
- **額度**：使用者是 Pro 方案。五小時額度到 90% 時，用 scheduled task 排在重置後約 5 分鐘叫醒協調對話。叫醒後要**繼續把工作做完**，不只是審查。
- **effort**：子 session 的 effort 不能高於協調對話自己的。協調對話要設成 high，派出去的 session 才會是 high。

## 2. 工作（依類型）

### 2.1 實驗：E6／E7（#732 主線）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
|---|---|---|---|
| #732 FEAT-EXP-RUN（PR [#741](https://github.com/Polalalabear/amidst/pull/741)，`claude/feat-exp-run`，Draft） | E6 12 段＋3 段診斷錄製、API 各組、評分、統一分析、Colab 結果 | 第 1 輪零費用部分完成：AO-L 延遲歸零 0.2481 → 0.5741（仍低於 B1 0.7587）。G5 Colab 包建置器 `d0d47a01` 已審查通過（D392 白名單） | 等 G1–G4 |
| G5 E7 Colab 包（舊 16 段） | `local/evidence/e7-colab-pack-20261127/`（4253 檔、531 請求） | 完成，Sonnet＋Opus 審查通過 | **等使用者**上傳私人雲端硬碟，在 Colab 執行 Run All |
| G3 #721 各組（PR [#743](https://github.com/Polalalabear/amidst/pull/743)，`claude/feat-e6-arms`） | 去錨定、加歷史、加摘要三組的請求建構，以及 K=1 小型診斷 | Opus 定案 NEEDS_CHANGES（D398 四點）。原 session `local_1d45dee9-095e-4ecc-98c4-4cf350c52e1e` 修改中 | 修完 → Sonnet 複審 → 付費跑診斷（上界約 USD 7.88） |
| G1＋G2 E6 路線與干擾者（`claude/feat-e6-routes`） | 設計文件 `E6_ROUTES_DESIGN_20261127.md`、`configs/evaluation/e6_routes_v1.json`、錄製器支援、1 段診斷錄製 | session `local_7b1915af-6532-483a-92bc-33210b59f514` 進行中，還沒開 PR | 設計要 Opus 審過才能錄 12 段正式資料 |
| G4 `run_all.sh` Stage 2／3 接線 | 一鍵執行：3 段診斷 → 自動凍結 → 12 段正式 | 未開始 | 等 G1–G3 |

### 2.2 8785 demo 與 LIVE（#735）

- 8785 已換 pin 到 `5727fc9a`（含 #714 前台 3D），gate r5 是 `local/evidence/gate-pin-20261127-r5/RESULT.txt`（SHA-256 `53e5a7be…04c6`），正在運作。
- #735 剩下：#675 Agent 預設設定（等 #732 的最佳設定），#566／#574 LIVE A／B 畫面（blocked，等 R2 #589）。

### 2.3 重現包與清理（#733）

- PR #738 已合併 `a90a7884`（盤點工具＋Linux／macOS 重現包）。#728 剩下雲端位置補登和分析後定稿。
- D394：`local/` 必要性審查後，使用者決定全刪、不留備份（約 8.2 GB），已執行，磁碟可用約 16 GiB。刪除腳本 `local/evidence/delete-20261127/delete.sh`。引用這些項目的文件之後標成「已刪除（D394）」。
- [#740](https://github.com/Polalalabear/amidst/issues/740)（Neon）：盤點工具的兩個引用盲點。

### 2.4 報告（#734）

- PR #736 骨架已合併 `c741c95d`。E6／E7 數字等 #732 跑完再另開 PR。小 nit：文件裡「等 #726 合併」要改掉。

### 2.5 Codex 與 Neon

- Neon：#740。#731、#733、#734 本輪的 PR 都已合併。
- Codex：額度不足，原本的 #732、#735 工作由 Claude 代做（D391、D396）。

## 3. 排程

- `amidst-coordinator-resume-0955`：2026-11-27 09:55 叫醒**舊**協調對話。交接後要改成叫醒新對話，或刪除後重建。

## 4. 本段教訓

- 審 #737 時只核對了修正項目，沒有比對 #731 原本承諾的範圍，結果 #732 開工後才發現 G1–G5 不在 main 上。之後審 feature PR 時，要把 issue 的「包含」清單逐項對到 diff。
- 交給使用者跑的指令曾給錯啟動檔（`start_demo.command`）。D395 之後改成由 Claude 自己執行。
