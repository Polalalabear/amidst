# A4-1／B4-1 預錄 Q2 Agent 候選為 0：診斷紀錄（#629）

日期 2026-11-20；基準 `origin/main` @ `7ef1426b`（含 #625 `1d322837`）。只讀診斷：不改 GT、不改圖、不渲染、不付費、不起 gateway。

## 結論

**類別：篩選條件（核定閘門），不是資料缺漏，也不是 ROI／bbox 座標問題。** 候選在第 4 層（`transition_candidates` 的核定閘門）全數歸 0。

`src/amidst/q1q5/candidates.py`：`scope_unapproved = scope is not None and (scope['G4_approved'] is not True or graphs.approval_status != 'APPROVED')`，成立時每條符合出口區的轉移都記為 `GRAPH_NOT_APPROVED` 並排除。目前三個條件都不成立：

- `tracking_scope_v3_1.json`：`G4_approved=False`、`status=PROPOSED`；
- `camera_graph_v3_1.json`、`region_graph_v3_1.json`：`approval_status=DRAFT`、`approval_ref=None`。

#625 把 scope 重新附上後，session 不再停在 `TRACKING_SCOPE_MISSING`，往下走到候選計算，才暴露這道閘門。這是 fail-closed 的預期設計（圖未經 G4 核定就不產生候選），#625 的 demo 核定只涵蓋 Q5 參數集，沒有核定圖。

**即使繞過閘門，仍是 0。** 圖上 22 條轉移的有效授權（`graphs.transition_authorities`）為：20 條 `TOPOLOGICAL_ONLY`（`edge_path` 為空）、2 條（`T_CAM_W1__CAM_W2`、`T_CAM_W2__CAM_W1`）`UNKNOWN／SAME_REGION_TRANSITION_NOT_APPROVED`；`path_traversability` 不是 UNKNOWN／TOPOLOGICAL_ONLY 的轉移 = 0 條。所以要讓 Agent 有候選，需要的是圖的核定與 edge-path 授權（人工 G4 決定），不是改程式。

## 每層人數（person、score≥0.3，出口判斷 `exit_boundary_inclusive=True`）

| 層 | 內容 | A4-1 | B4-1 |
|---|---|---|---|
| L1 | scope 內相機的 person 觀測 | EXT_CAR 17、EXT_CLEAR 63、W1 45 | BRANCH 5、R101_IN 12、W1 23、W2 47、WIDE 34 |
| L2 | bbox 底邊中點落在出口區 | W1 8（EXT_CAR、EXT_CLEAR 為 0） | BRANCH 3、R101_IN 2、W1 4、W2 18、WIDE 32 |
| L3 | 與出口區、scope 相符的轉移（有出口區命中的觀測合計） | 16 | 118 |
| L4 | 通過核定閘門後的候選 | **0**（16 筆全為 `GRAPH_NOT_APPROVED`） | **0**（118 筆全為 `GRAPH_NOT_APPROVED`） |

L1→L3 有人數，代表索引 bbox、ROI 像素座標、scope 相機清單是對得上的；在 L4 才變 0。
旁註：A4-1 的 EXT_CAR、EXT_CLEAR 共 80 筆 person 觀測沒有任何一筆落進出口區，這是另一個現象（行人沒走到出口區，或出口區沒涵蓋其路徑），但不影響結論，因為即使有，L4 仍為 0。

## 對照 B-05

B-05（runs[0]，P1 v4）沒有 Agent 決策點（`scripts/serve_demo_integration.py` L240 的註解：CL-B16 / #620），不走 `transition_candidates`，所以不是對照組可比的 0。未另跑。

## 可重現指令（只讀）

```bash
git clone --shared --no-checkout ~/amidst <scratch>/clone && cd <scratch>/clone
git remote set-url origin https://github.com/Polalalabear/amidst.git && git fetch origin main && git checkout origin/main
AMIDST_DEMO_HOME=~/amidst/local/data/demo-owned-v1 PYTHONPATH=src:scripts ~/amidst/.venv/bin/python scripts/diag_629_agent_candidates.py
```

診斷只用偵測索引的 bbox 與已 pin 的圖；未讀 GT、渲染軌跡、可見性或深度，也沒有接進推論路徑。

## 修法選項（不由本紀錄決定）

1. **維持現狀（建議的 demo 說法）**：預錄 Agent 在 A4-1／B4-1 的決策點因「圖未核定」而無候選，UI／報告把原因顯示為 `GRAPH_NOT_APPROVED`，而不是顯示「沒有候選人」。零推論輸入變動。
2. **取得 G4 核定**（人工決策，Opus／使用者）：核定 `camera_graph_v3_1`／`region_graph_v3_1`／`tracking_scope`，並為 W1↔W2 與其他轉移補 edge-path 與授權。會改變推論輸入（候選集合），須走決策流程；不是本 issue 範圍。
3. **demo 專用核定（類似 #625 的 `demo_approved`）**：只對 A4-1／B4-1 把圖標為 demo 核定。會改變候選範圍與推論輸入，且 20 條 `TOPOLOGICAL_ONLY` 仍會被排除，只剩 0 條可通行（W1↔W2 也是 UNKNOWN），**效果仍是 0**，除非另外授權 edge-path；不建議。
