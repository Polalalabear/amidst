# 研究歷程與分支封存（D176）

本文按研究階段整理 2026-10-02 到 2026-11-09 的工作，供日後查證據時定位。每一段寫期間、目的、結果與轉向原因，並附 1–3 個關鍵標籤。逐支分支與 SHA 的完整對照不寫在本文，見自動產生的 [`branch_archive_map.csv`](branch_archive_map.csv)（2026-11-09 快照；刪除後重跑 `plan` 只會列出仍存在的分支，因此 CSV 以這次提交的版本為準）。

## 封存方式

整理前的盤點（每支分支的作者、commit 數、PR、標籤與引用位置）見 [`branch_inventory_before_20261109.csv`](branch_inventory_before_20261109.csv)。

2026-11-09 整理前，遠端共有 106 支分支、30 個標籤。整理後保留 18 支分支，刪除 88 支，新增 17 個附註標籤，原有 30 個標籤不動。刪除的分支，其末端都是 `mainline/q1q5` 或 `main` 的祖先，或被某個標籤包含；文件、實驗紀錄與 #93、#445、#479、#488 留言引用的 328 個 commit，整理後全部仍可從 mainline、main、標籤或保留的分支到達。

階段結束標籤（`archive/<階段>-…-end`）若需要同時保存多支未合併分支，會指向一個合成的 merge commit：它的 parent 是該階段被刪分支中、其他 ref 都到不了的末端，tree 取最新一個 parent 的 tree。這個 commit 只掛在標籤上，沒有合併進任何分支。

要還原任一支分支，從 CSV 的 `restore` 欄取指令，例如：

```bash
git push origin <tip_sha>:refs/heads/<branch>
```

或用 `python3 scripts/history/branch_archive.py restore --map docs/history/branch_archive_map.csv --branch <branch>` 印出指令。

## 階段

### 一、第一階段：學校場景模擬與整合強化（2026-10-02 至 10-14）

這一階段以 `blender/school_v3.blend` 為唯一來源場景，建立綁定來源的語意幾何、物理政策與 Case 1–3 的有界流程。Phase 2 整合強化在 10-06 凍結（723 項測試通過），Case 1–3 的有界流程在 10-14 驗證並凍結，相關斷點已有 `checkpoint/phase1/*` 系列標籤。結果是一條可重現的幾何與物理驗證鏈，但它不是正式的 Case 1–3 研究基準，也不能直接展示跨鏡頭追蹤。之後工作轉向能在工作台展示的 Office 雙鏡頭 demo。

標籤：`phase1-scoped-case123-20261014`、`archive/p1-school-scene-end`

### 二、Office demo K1–K7 與受控場景 r003（2026-10-16 至 10-20）

目的是在 Office 場景選一個來源觀測，跨兩支分離的鏡頭穿過盲區，並在工作台分清觀測、推論、`MISSING` 與 `UNKNOWN`。這段時間完成 K1 盲區假設模組、K5 畫面牆、K6 展示模式、K8 合成場景、C5／C6 的 5 Hz 多鏡頭可行性篩選，並在 10-18 做了一次現場預演。接著用受控場景 r003 做 D47 篩選、CS-B 人工審查頁與 K7 地圖驗證，也起草了工作台 v2。10-20 的 D63 把 Q1–Q5 定為首要目標並暫停 3D 線，這一段因此收尾。

標籤：`archive/office-demo-visualization`（既有）、`archive/office-k7-r003-verification`、`archive/office-k1-k7-end`

### 三、Q1–Q5 問題轉向與 L2 評分（2026-10-20 至 11-02）

D63 之後，研究改以五個具體問題（Q1–Q5）驅動，先定查找預算、HSV 顏色訊號的限制、Q5 切鏡狀態機與 L2 連結器／控制器契約。10-27 起分成兩條線，陸續做出 Q5 切鏡評分 v2、L2 腳本轉接器與報告彙整檢查（CQ-32／33／36），以及情境卡與架構規格。許多提案以草稿 PR 形式審查後關閉，採用的內容另行進入 mainline，未採用的版本由標籤保存。11-04 demo 的期限逼近後，工作改成以功能為單位整合。

標籤：`archive/q1q5-q5-switch-eval-v2`、`archive/q1q5-pivot-end`

### 四、r004 受控場景、yyin 標註包與 r005（2026-10-21 至 11-06）

r004 是八支鏡頭的受控場景，目的是在已知的靜態拓撲上檢驗跨鏡頭連結。這段時間提出各鏡頭的靜態圖與出口、L2 靜態可行性分析與 v4 圖草稿，並做出確認用疊圖，交給 yyin 人工確認。G4 收據依 D101 選用選項 A，yyin 的 Q1–Q3 主標註包也在這段時間完成。11-06 另提出 r005 人物短片參數，該分支仍待 Codex 確認，暫時保留。

標籤：`archive/r004-yyin-main-pack`、`archive/r004-g4-receipt`、`archive/r004-controlled-scene-end`

### 五、11/04 demo 整合（2026-11-01 至 11-04）

為 11-04 的第一次 demo，工作改成以功能為單位的 PR（D104），FEAT 議題 #369–#376 各自整合進 demo。FEAT-4 複雜情境是最大的一支，demo 紀錄多次引用；FEAT-8 延伸候選與專案文件包也在這時完成。demo 結束後，D126 把系統核心縮為兩件事，其他方向暫停。

標籤：`archive/demo1104-feat-4-complex`、`archive/demo1104-integration-end`

### 六、核心：追蹤與查找（2026-11-04 至 11-07）

D126 把系統核心定為「追蹤」與「查找」，Claude 寫契約與測試，Codex 實作，第一版核心實作與 CX-8 追蹤轉接器在 #411。D127 建立 Argon／Codex 拉取佇列（#412–#433），由 Argon 做 Windows 乾淨 clone 基準、Colab 一鍵筆記本、M1–M4 基準、Q4 評估工具與研究圖表，Codex 做本機建置腳本、安全資料包、追蹤評估與獨立預覽（#445）。其中 11-06 之後仍有更新的 Argon 與 Codex 分支暫時保留，待各自確認後再刪。核心可用之後，工作轉到新介面與 demo 驗收。

標籤：`archive/core-d126-search-track`、`archive/core-track-search-end`

### 七、新介面、驗收 A 與第一期收尾（2026-11-07 至 11-09）

這一段把新工作台 UI 從規格做到 `claude/ui-redesign-v1`，接上 D139 計數、D145 重新鎖定、D147–D149 後端修正與量測 B 的頁內延遲工具。依賴改為 Python 3.12 的自有鎖檔（Epic C），使用者在 11-08 通過驗收 A。第一期收尾包括 P2 修正、CI 與來源紀錄、Agent 決策設計、檔案帳冊與清理閘門（D163），mainline 在 `6e852328` 完成第一期。實驗紀錄 v3 仍在 #488 上進行，該分支保留。

標籤：`archive/accept-ui-redesign-spec`、`archive/accept-ui-487-p2p3`、`archive/accept-phase1-done`

### 八、暫停或放棄的路線

有三條路線沒有進入 mainline。3D 線在 D63 暫停，內容封存在 PR #81 的封存分支。#397 模型實驗企劃已寫到事件設計，後來隨 D156 研究計畫一起暫停。Epic D 的自然語言路徑 (b)（#490）是標示不合併的開放 PR，分支保留，等待決定是否重啟。

標籤：`archive/paused-3d-line`、`archive/paused-model-experiment-plan`

## 保留的分支

保留 18 支，理由寫在 CSV 的 `keep_reason` 欄：

- `main`、`mainline/q1q5`；`claude/ui-redesign-v1`（8785 從這支執行）；`claude/445-demo-integration`（開放 PR #488、#490 的 base，刪除會關閉它們）。
- 開放 PR 的 head：#488、#490、#505、#506。
- 11-06 之後仍有更新的 `codex/*` 與 `argon/*` 共 10 支，待 Codex／Argon 確認。

## 重新產生

```bash
gh pr list --state all --limit 1000 --json number,headRefName,state,baseRefName,title > prs.json
python3 scripts/history/branch_inventory.py --prs prs.json --out inventory.csv
python3 scripts/history/branch_archive.py plan --inventory inventory.csv --out docs/history/branch_archive_map.csv
python3 scripts/history/branch_archive.py verify --map docs/history/branch_archive_map.csv --write
```
