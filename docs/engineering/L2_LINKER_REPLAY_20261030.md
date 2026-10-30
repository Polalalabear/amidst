# CQ-38：P1 現行參數離線 linker/controller 重播

#333；接 #273@`9a762fbe2bbeca887e191c755aebe015f6089c8c`。結果為 ENGINEERING_ONLY，替代方案比較 **INCOMPLETE**，不構成參數核定、品質改善或正式驗收。

## 來源與執行

只讀 P1 可攜包 v4 manifest（SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`），recording `2777741d96ac9aff5bffb2f61a4d2938`，index manifest／320 格 records、parameter、clock、region/camera graph、registry。先驗 manifest/member pins，再由原 JsonRunStore、ClockMapping、load_graphs 與 RuleController 執行；Q4 port 直接呼叫 candidate_evidence。沒有讀 RGB、GT、劇本、visibility/depth，沒有新偵測、模型呼叫或產品程式改動。

來源錄製產品為 `c26d7cdd07deb43c9991a4f46403ea0236277fb1`，本次用 #273 的已交件產品快照。原 saved request 已去掉瀏覽器 session_ref；這次指定 LOCAL session 並沿用來源錄製第一個 ON_CAMERA observation 作為明確 seed，故 session IDs 不同，**不宣稱與歷史錄製逐 bytes 相同**。現行重播與歷史錄製的 LINKED pair 集合相同、下列所有計數差異為 0。

## 結果與計數定義

| 指標 | 現行參數 | 歷史錄製 | 差異 |
| --- | ---: | ---: | ---: |
| LINKED observation pairs | 56 | 56 | 0 |
| 連續 LINKED journal runs | 14 | 14 | 0 |
| ON_CAMERA timeline segments | 14 | 14 | 0 |
| 進入 SEARCHING | 4 | 4 | 0 |
| RETURN_TO_ORIGIN accepted actions | 3 | 3 | 0 |
| SWITCH accepted actions | 1 | 1 | 0 |

LINKED pair 以 camera/prev/next observation 定義；連續 runs 在非 LINKED row 或 local segment/camera 變更時切開，不是把每個成功 pair 都稱作一段。SEARCHING 僅計 accepted 且 state_before != SEARCHING、state_after == SEARCHING；RETURN 使用 wire action RETURN_TO_ORIGIN。所有指標均非 GT 正確性或身分確認。

9 個 opt-in 方案：score 0.39/0.38/0.35/0.30，IoU 0.299/0.25/0.24/0.225，組合 0.30+0.225。新記憶體內 parameter set 保留 PROPOSED，清除 baseline approval_ref/approved_by，重新計 content hash；原參數文件不改。逐一呼叫**原 controller**均回 PARTIAL/PARAMETERS_NOT_APPROVED，timeline/journals 為空；metrics/delta/new_linked_pairs 都是 null，不把拒絕的空輸出算成改善為零或更差。較低 index floor 0.10 因 raw below floor 不存在維持 NOT_RUN。

## 守門衝突與待決

#333 要求 opt-in 完整比較，但現行 LinkParameters.from_document 與 RuleController 只接受 APPROVED；#273 明示替代值 PROPOSED。程式不複製原 synthetic approval 到改過數值、不偽造 approval_ref、不 monkeypatch/subclass 繞過守門。完成替代方案實際 session 結果需要使用者核定工程比較用的獨立 parameter sets，或由協調者核定另一條隔離實驗契約；詳見 #333 偏離提案。此處的合成單元測試沿用 repo 既有 test-only fixture，不能作為 P1 參數核准。

## 重現

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python scripts/replay_l2_linker_options.py --source-root '/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試' --output /private/tmp/amidst-01a180f1/cq38/replay-b --sweep
```

以新輸出目錄 replay-c 再執行，11 個檔案逐 bytes 相同；report SHA-256 `43228871ff999568ff168bf0b7f291ea74d32d3d9d17fa1bd6ef09abf24ae737`。輸出目錄須尚不存在。未加 --sweep 僅跑現行 baseline；flags 不改產品預設。native-domain LOCAL 輸出保留 response/journals/snapshots/evidence/seeds/diagnostics，但依時序與雜湊邊界去除 response.stats、diagnostics[].stats 的 wall latency；不是 registered API recording 或 formal freeze。既有來源 bytes 執行後逐檔再驗。

`AMIDST_REQUIRE_IMPL=1 ... python -m pytest -o addopts='' -q -p no:cacheprovider tests/q1q5/test_l2_linker_replay.py tests/q1q5/test_l2_detection_options.py`：28 passed。原 controller、LocalLinker.step 與實際 Q4 evidence 均執行，涵蓋網路禁止、預設單一 baseline、PROPOSED 不升權、RETURN wire、run/pair 區分、兩次穩定輸出、來源 pin/symlink 拒絕。

架構守門 NOT_RUN（#307 尚未交付）；#127 NOT_RUN（工程 native-domain audit，未產生 registered API recording／正式 freeze）。未跑替代值的有效 session、raw-floor 推論、recall/誤接/身分評估、browser、formal/AC7、Claude 獨立複審。完整輸出留 LOCAL `/private/tmp/amidst-01a180f1/cq38/replay-b` 與 `replay-c`，GitHub 僅程式、測試、摘要與 pins。
