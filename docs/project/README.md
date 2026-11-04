# Amidst 專案文件包（2026-11-04，D126 版）

**一句話定位**：Amidst 是一個多攝影機證據工作台，幫使用者在多台監視鏡頭裡**快速知道目標大概在哪**。它是輔助工具，不求精確，每個答案都能追溯到來源畫面。

本文件包依使用者 2026-11-04 的決策 [D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) 整理，用來對外說明專案目標與架構。

## 兩個核心（D126）

| 核心 | 使用者做什麼 | 系統給什麼 |
| --- | --- | --- |
| **case1 查找** | 選時間範圍（必填），加上地點或特徵（至少一個） | 時間範圍內拍到目標的鏡頭畫面 |
| **case2 追蹤** | 選特徵（必填），地點可空，時間空著代表現在 | 單畫面自動切到看得到目標的鏡頭；多畫面列出所有找到目標的鏡頭；盲區時顯示俯視圖和物理預測曲線 |

其他工作（M1–M4 實驗、Q4 正式標註、Colab 包、大整理後半）都已擱置，見 [ROADMAP.md](ROADMAP.md#擱置清單)。

## 文件導覽

| 檔案 | 給誰看 | 內容 |
| --- | --- | --- |
| [PRD.md](PRD.md) | 所有人 | 問題、目標使用者、定位、兩個核心的使用情境、非目標、成功標準、展示範例 |
| [SPEC.md](SPEC.md) | 開發者、審查者 | 輸入欄位與驗證、輸出、證據狀態、宣告時鐘、倍速、畫面規則、介面契約 |
| [SYSTEM_ARCH.md](SYSTEM_ARCH.md) | 開發者 | 架構圖、資料流、地點查找、GT 隔離、分支規則、分工 |
| [ROADMAP.md](ROADMAP.md) | 使用者、協調者 | 大任務與 test gate、擱置清單、使用者節點 |
| [DECISIONS.md](DECISIONS.md) | 所有人 | D113～D126 重要決策摘要與 #93 留言連結 |
| [GLOSSARY.md](GLOSSARY.md) | 所有人 | 術語表 |
| [BUILD_FROM_SCRATCH.md](BUILD_FROM_SCRATCH.md) | 要重現的人 | 從 Blender 建檔、路線、渲染、標記、驗證到啟動工作台的完整步驟；repo 裡缺的步驟標 UNKNOWN |

## 怎麼啟動 demo

本文件包不重寫啟動步驟，請直接看下列兩個來源：

- **運行手冊**：[`docs/operations/DEMO_RUNBOOK_20261104.md`@`796cc17`](https://github.com/Polalalabear/amidst/blob/796cc176cd40bedbfe701b95192d3c8679755aa9/docs/operations/DEMO_RUNBOOK_20261104.md)。§0 列出三段（A 錄製伺服器 8766、B live 追蹤 8765、C 複雜事件播放 8780），§1 是事前檢查清單，§2～§4 是各段的啟動指令。
- **一鍵啟動**：`start_all_demo.command`，在 [PR #408](https://github.com/Polalalabear/amidst/pull/408)（head [`eb10d4c`](https://github.com/Polalalabear/amidst/blob/eb10d4c62ce09a765488cdd0548cfdd3abfd5109/start_all_demo.command)）。它照運行手冊 §2／§3／§4 的參數一次啟動三段，Ctrl-C 關掉全部子進程，不讀 OpenAI key。手冊在同一個 PR 新增 §8.1「一鍵啟動與事件選單」。**#408 截至本文件撰寫時仍是 OPEN、尚未合進 `mainline/q1q5`**，所以 mainline 上還沒有這個腳本。

demo 需要的 P1 v4 包和 CX-7 safe RGB 都是 LOCAL 資料，不在 repo 裡（手冊 §0、§1）。

## 目前狀態（2026-11-04）

| 項目 | 狀態 | 出處 |
| --- | --- | --- |
| 整合分支 | `mainline/q1q5` = `796cc17`（#405、#407 已合併） | [D125](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251) |
| 11-04 demo | 三段：監控牆／查找／B-05b 預錄切鏡、B-05a live（預期 fail-closed）、複雜事件唯讀播放 | 運行手冊 §0@`796cc17` |
| 工作台整合（事件選單、查看／追蹤／查找、倍速、宣告時鐘） | PR #408 OPEN（draft），未合併 | [#408](https://github.com/Polalalabear/amidst/pull/408) |
| 核心契約 `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md` | 已由 [PR #410](https://github.com/Polalalabear/amidst/pull/410)（`b1a619d`）併入：`docs/contracts/Q_CORE_SEARCH_TRACK_V1.md` 與 `docs/contracts/schemas/q-core.search-track.v1.schema.json`，狀態 PROPOSED（Codex 確認後生效） | [D126-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) |
| 物理預測路由 `q_physical_prediction` | 回 503（`Q_RESOURCE_UNAVAILABLE`），先當佔位 | `src/amidst/q1q5/api.py`@`796cc17` 第 24、329 行 |
| 複雜事件 A4-1／B4-1 真實追蹤 | 先重渲染再跑 #118 → CX-8；尚無追蹤輸出 | [D124](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061) |
| 擴充 Office 場景（多間教室＋COCO 物件） | 已指派 Codex，尚未產出 | [D126-2](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) |

## 事實來源與寫法

- 本包的 repo 事實都在 `mainline/q1q5`@`796cc176cd40bedbfe701b95192d3c8679755aa9` 讀取，下文簡寫為 `@796cc17`；其他分支會另外寫出 SHA。
- 決策與協調取自 [#93](https://github.com/Polalalabear/amidst/issues/93)、[#279](https://github.com/Polalalabear/amidst/issues/279)、[#408](https://github.com/Polalalabear/amidst/pull/408) 和 [#397](https://github.com/Polalalabear/amidst/pull/397)（研究企劃，head `e6c6ad0`）。
- 讀不到的寫 **UNKNOWN**，還沒產生的數字寫 **待補**。本包沒有新的實測數字。
