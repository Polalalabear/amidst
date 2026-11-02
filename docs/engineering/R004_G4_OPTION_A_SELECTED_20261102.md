# r004 G4 選項 A 選定副本（D101-2 第 2 步；2026-11-02）

**PROPOSED；尚未生效的選定草稿，不是正式 G4 回條。**
依 [D101-1／D101-2](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6552319555)、[D105-3／D105-5](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556609083) 與 [D111](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6558961025)，只提交選項 A 的選定副本，供固定 head 複核及之後的 checkpoint 使用。

選定檔：`docs/engineering/R004_G4_OPTION_A_SELECTED_20261102.json`。

- `decisions_sha256`：`9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c`
- JSON 檔案 bytes SHA-256：`d8753a21fe0abe1fdad5215e9d41473f5d4ed643de68bffe6aa43cf6edf2ba8b`
- 原草稿：`docs/engineering/R004_G4_RECEIPT_DRAFT_20261028.json@ac70ed75e4503ab54ec58c08ec58957c179bb72c`；bytes SHA-256 `05dbf66fa041cb0d19ddbf9da2e0c459a0d680be320eb9ddac668f55d6a41433`，保持不變。原 Markdown 同樣保留原 bytes，描述的是當時未選定狀態。
- 格式：`docs/contracts/Q1Q5_D86_G4_RECEIPT_PROPOSAL_20261027.md@d560f224be0f93cf62076f5ae2fa78b0ae957d15` §3–§3.2 的既有五鍵白名單。沒有加入 CQ-21a 新 gate 欄位。
- 圖：`#294@0c34287b0b0c21c672f863fd281934f37e8aa24b`。全部 source／catalog／static／兩圖／scope／run pins、方向、出口入口及路徑繼承草稿，不改圖檔。

## 選定範圍

以下「選定」只描述待複核 payload 的值，不表示 G4 已生效。
run A4＝`ctrl-lcorr-s1-a4-5fps-v1-r004`；B4＝`ctrl-lcorr-s1-b4-5fps-v1-r004`。

| 邊 | traversability / state | run_ids |
| --- | --- | --- |
| E_OUT_VEST、E_VEST_CORR | APPROVED_WALKABLE / OPEN | 只列 A4 |
| E_W_CORNER、E_PORTAL_R101 | APPROVED_WALKABLE / OPEN | 只列 B4 |
| E_CORNER_N | NOT_APPROVED / NOT_APPROVED | 保留草稿範圍；不核准 |
| E_PORTAL_R102 | TOPOLOGICAL_ONLY / UNKNOWN | 保留既有限制及範圍 |

選定邊使用契約已有的 `APPROVED_WALKABLE`／`OPEN` 詞彙；回條中 E_CORNER_N 的 `NOT_APPROVED` 是 D101 的明確不核准決定，不寫回 graph enum。

| run | decision=APPROVED 的 transition_id（只列自己的 run） |
| --- | --- |
| A4（4 條） | T_CAM_EXT_CAR__CAM_W1、T_CAM_EXT_CLEAR__CAM_W1、T_CAM_W1__CAM_EXT_CAR、T_CAM_W1__CAM_EXT_CLEAR |
| B4（12 條） | T_CAM_BRANCH__CAM_W1、T_CAM_BRANCH__CAM_W2、T_CAM_R101_IN__CAM_W1、T_CAM_R101_IN__CAM_W2、T_CAM_W1__CAM_BRANCH、T_CAM_W1__CAM_R101_IN、T_CAM_W1__CAM_WIDE、T_CAM_W2__CAM_BRANCH、T_CAM_W2__CAM_R101_IN、T_CAM_W2__CAM_WIDE、T_CAM_WIDE__CAM_W1、T_CAM_WIDE__CAM_W2 |

- M1 `T_CAM_W1__CAM_W2`、`T_CAM_W2__CAM_W1` 各自為 `UNKNOWN`，保留 B4 範圍及原有空 edge_path，不開放。
- 其餘 4 條轉移為 `NOT_APPROVED`，run_ids 保持原有 `[]`。
- 全部 7 個 region 的用途決定為 `UNKNOWN`；R101 用途仍未核准，不由 E_PORTAL_R101 通行選定推導。
- 所有位置的 `allowed_purposes` 與頂層 `approved_purposes` 均為 `[]`；兩個 run 的 `derived_legal_transitions_by_run[].transition_ids` 均為 `[]`。
- 頂層 `status=PROPOSED`，schema_version 沿用 draft.v1；`approval_ref`、`human_decision_ref`、`independent_review_ref` 仍為 null。沒有偽造核准／複核。
- recommendation／yyin_opinion 是原草稿的歷史旁欄，不進決定 hash，也不授權。date 與 producer 只描述選定副本產製，不是核准日期。

## 重算與複核

原草稿 Markdown 的「Hash、選定payload與後續流程」內附獨立重算程式；將其 `Path(...)` 改為本選定 JSON 路徑，即以相同五鍵白名單重算上述 `decisions_sha256`。canonical JSON 為 `sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=True`、`allow_nan=False`，UTF-8 bytes 不含尾端換行。檔案 bytes hash 與決定 payload hash 是不同值。

依 [#386 協調者驗證指示](https://github.com/Polalalabear/amidst/pull/386#issuecomment-6559142741)，在**拋棄式驗證 clone 的獨立分支**（以 #348 的待複核 head 為起點）依序合入下列 heads；不推送驗證分支，不把檢查器合入 #348 原分支：

```json
[
  {"pr": 352, "head": "97557fc796cf9dde3212297b47af23a4a5bb6a78"},
  {"pr": 386, "head": "ab705b30bc7f418a4c81d06bd81603965c8f1527"}
]
```

```bash
git merge --no-ff 97557fc796cf9dde3212297b47af23a4a5bb6a78
git merge --no-ff ab705b30bc7f418a4c81d06bd81603965c8f1527
uv run --no-project python scripts/check_g4_option_a.py docs/engineering/R004_G4_OPTION_A_SELECTED_20261102.json --git-repo .
AMIDST_REQUIRE_IMPL=1 AMIDST_G4_RECEIPT=docs/engineering/R004_G4_OPTION_A_SELECTED_20261102.json uv run --no-project python -m pytest -q tests/q1q5/test_g4_option_a_t.py
git diff --check ac70ed75e4503ab54ec58c08ec58957c179bb72c <待複核的348-head>
```

檢查器只驗選定範圍、hash、圖 pin 與禁用鍵，不驗 G4 已生效。測試使用既有 Python／pytest 環境；不另建 venv。

## 尚未成立的 gate

1. Claude 以 #348 新固定 head 複核本 hash（D101-2 第 3 步）。
2. 使用者在 checkpoint 留言引用此新 hash（第 4 步）。
3. 協調者在 #93 記 D 決策，引用同一 hash 與使用者留言 ID（D105-5 第 5 步）。

原待決 hash `7ea8c5e5e37238f406170367563efa58c73be42ef890ffe431d58f8fb18f6323` 與參考 hash `f1e0bfe6…09a3` 不能用來核准此副本。
此五鍵 hash 只供 D98-2(a) 的 G4 渲染前置；CQ-21 實作前，依 D105-3／D101-3 用 B1 新白名單重算並請使用者重核，產品端仍不開放跨鏡頭切換。
沒有渲染、正式資料、模型執行、AC7／研究驗收、身份或物理安全結論，也不授權任何整合分支合併。
