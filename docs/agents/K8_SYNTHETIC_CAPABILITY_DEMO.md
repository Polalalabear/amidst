# K8 合成能力展示：設計文件（D23）

- 狀態：設計階段（本文件只寫設計，不含程式）；2026-10-17
- 依據：#26 的 D19（更正版）、D21、D22、D23；[Office demo 計畫](OFFICE_DEMO_PLAN_20261101.md)；K0 盲區假設契約 v1／v1.1
- 撰寫：Claude Code（Opus 5.5，high effort），由協調 session 指派
- 範圍：(1) 查清真實人形 run 為什麼只有 1 條代表假設；(2) 設計 S1／S2／S3 三個合成情境、合成真值評估、標示與隔離、交付方式、任務拆分。本文件的數字都是**實際執行 K1／K5 的結果**，執行方式見 §0。

## 0. 執行環境與可重現性

| 項目 | 值 |
| --- | --- |
| 程式碼來源 | `git archive origin/codex/c5-d21-strict-visibility`（#53 @ `ce766f9`，含 #50 與 C4b），匯出到 session scratchpad（LOCAL） |
| K1／K5 版本 | 主要：`src/amidst/blind_hypothesis/engine.py` blob `1f0f674`（與 `claude/k5-pruning` @ `726e390` 相同）。**複跑**：K1 新 head `claude/k1-restricted`（#48 @ `74c6ace`，engine blob `491cc94`、`retrieval_evidence.py` blob `87d83f2`），另以 `git archive` 匯出。§1 的診斷與 S1／S2／S3 在兩個版本上的條數、長度、剪枝結構、面積完全相同；`output_sha256` 不同，因為 74c6ace 的回應多了 restricted-policy 欄位。`_string_pull` 到 `_route_pool` 這段兩版逐行相同 |
| 地圖 | C7 `docs/engineering/C7_OFFICE_SOURCE_MAP_20261017.json`，SHA-256 `53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61`，variant `person`。#40 `codex/c7-source-map` @ `4c54166` 的同名檔案 hash 相同 |
| 設定 | `configs/office_person_blind_hypothesis_v1.json`（速度 0–2.0 m/s、grid 0.25 m、`min_separation_m` 0.75、`max_candidate_paths` 256、time_step 0.2 s） |
| 直譯器 | `/Users/polalabear/Developer/amidst-claude/.venv/bin/python -I`，腳本內以 `sys.path` 指向匯出目錄；每支腳本都 assert／印出 `amidst.blind_hypothesis.engine.__file__` 位在匯出目錄 |
| 真實 run 資料 | `/Users/polalabear/Developer/amidst/data/engineering/office_person_20261016_v1/office`（唯讀載入，`load_scene` 只讀 JSON，不讀影像、GT 或 renderer 軌跡） |
| 試跑腳本 | 共用 notes 資料夾 `k8_probe_scripts/`（LOCAL，不進 repo）：`real_run.py`、`diag.py`、`diag60.py`、`k8lib.py`、`s1.py`、`s2.py`、`s2b.py`、`s3.py`、`truth.py`、`truth_diag.py`、`k1r_all.py`（74c6ace 複跑） |
| 確定性 | S3 腳本連跑兩次，三個回應的 `output_sha256` 逐位相同：1f0f674 上是 `af40b2ca…`、`a811ba6a…`、`016f27e4…`；74c6ace 上（`k1r_all.py`）是 `a64e133e…`、`ab271adc…`、`9c1fd9df…` |

74c6ace 的匯出沒有 `configs/office_person_blind_hypothesis_v1.json`，複跑時從 ce766f9 的匯出複製同一個檔案到 scratchpad 的匯出目錄（hash 不變）。試跑時對 K1 內部函式（`_route_pool`、`_string_pull`、`_settle_anchors`）做了**記憶體內的唯讀監看**（包一層記錄後原樣回傳），沒有改任何檔案。改變 `min_separation_m` 的實驗也只在記憶體中複製設定，不是提案的新設定值。

## 1. 第一部分：真實 run 為什麼只有 1 條代表假設

### 1.1 對象與實際輸出

Office 人形 run `blender-contact-control-office-person-20261016-v1`，D18 端點 FRONT 4.6 s → REAR 8.2 s，盲區內部 4.8–8.0 s（17 步）。透過 `Workbench.call("target_reconstruction", …)` 呼叫 C4b（`top_k` 3），兩種模式：

| 項目 | `NONE` | `BASELINE`（D21 兩筆真實負證據） |
| --- | --- | --- |
| status | READY | READY |
| 代表假設 k | 1 | 1 |
| `rejected_counts` | speed 0、walkable 0、unseen 0、diversity 0 | 同左 |
| `limits.hit` | `[]` | `[]` |
| `min_separation_m` | 0.75 | 0.75 |
| `LATTICE_BUILT` | 858 格 | 858 格 |
| `ENDPOINT_CELLS` | start 469 格、end 367 格 | 同左 |
| `UNSEEN_MASK_APPLIED` | 0 筆證據、移除 0 格 | 2 筆證據、移除 0 格 |
| `ROUTE_POOL_BUILT` | candidates 1、`via_cells_excluded_by_separation` 60、`anchor_segment_rejected` 0 | 同左 |
| `REPRESENTATIVES_SELECTED` | k 1、passing 1 | 同左 |
| 唯一假設 | `hyp:5c0c78dd846f51ec1a35ea0a`：2 個頂點（直線），長 1.268555 m，平均速度 0.352 m/s，score −3.163802；unseen UNKNOWN | 同一條；unseen PASS |

端點本身：FRONT 是 `SEGMENT`／`FOOT_RAY_PIXEL_BAND`，長 0.738 m；REAR 是 `SEGMENT`／`HEAD_RAY_HEIGHT_PRIOR`，長 2.493 m。兩段最近點相距 1.27 m，而且兩段之間可以直接連線（直線完全在可走區內）。

### 1.2 候選池為什麼只有 1 條：逐格追蹤

`_route_pool` 依「經過 via 格的路線長度」排序逐格嘗試。每次嘗試先接起兩棵最短路徑樹、再 `_string_pull` 拉直、`_settle_anchors` 把兩端錨點移到端點區最近點，最後以拉直後的折線做 key 去重。監看結果：

| 實驗（只在記憶體中改設定） | 被間距略過 | 實際嘗試 | 拉直後頂點數 | 去重後不同路線 | via 鏈偏離最終路線 ≥0.75 m 的嘗試 |
| --- | --- | --- | --- | --- | --- |
| 原設定 `min_separation_m` 0.75 | 60 | 532 | 全部 2 | **1** | 531（最大偏離 4.12 m） |
| `min_separation_m` 0.25 | 12 | 580 | 全部 2 | **1** | — |
| `min_separation_m` 0.001（等於關掉間距略過） | 0 | 592 | 全部 2 | **1** | 531（最大 4.12 m） |

592 = 所有時刻可達格的聯集，與 Codex D21 報告的「聯集 592 格」一致，代表最後一列已經把每一個可能的 via 格都試過。

### 1.3 回答協調者的追問：那 60 個被略過的 via 格會不會藏著第二種走法？

先對照 Codex 的唯讀診斷：pool 只有 1 條、四類 `rejected_counts` 都是 0、`limits.hit=[]`、60 個 via 格因間距規則略過，以上**全部與本次重算一致**（ce766f9 與 74c6ace 兩版都一樣）。Codex 的結論是「不能證明地圖只有一種走法」，這句話本身沒錯；本節把它補完整：

**不會。** 把間距略過關掉（0.001 m）後，那 60 格連同其他 532 格全部實際嘗試，每一條都拉直成同一條 2 頂點直線，去重後仍只有 1 條。建池階段的間距略過**沒有**在挑選之前排除任何不同的走法。`rejected_counts` 全為 0 也因此合理：其他嘗試不是「沒通過檢查」，而是「拉直後和第一條完全相同」，在 `engine.py:1574` 的 `if key in seen: continue` 被默默丟掉，不計入 `rejected_counts`，也不進 trace。

即使 via 鏈偏離最終路線達 4.12 m，拉直也會把它拉回直線，原因是兩端錨點彼此可直視：`_string_pull`（`engine.py:1412–1443`）只要整段線段都在同一個區域內就直接連線，via 格不是必經點。

### 1.4 地圖上到底有沒有第二種走法？

用「同倫類」來看（也就是繞過某個障礙物的哪一側）：

- 時間預算：3.6 s × 2.0 m/s = 7.2 m；K1 的可達界再乘 `lattice_metric_factor` 1.0824，約 7.79 m。
- C7 person 地圖只有 1 個可走區域（329.77 m²），內含 6 個障礙物洞（4 張桌子各 6.56 m²、1 個 7.68 m²、1 個 1.68 m²）。從兩端點繞過任何一個洞的粗估長度（到洞的距離 + 半周長 + 回到另一端的距離）最短約 **13.1 m**，遠超過 7.79 m。
- 兩端點之間的直線在地圖內。

所以在這段盲區長度與這張地圖下，**只有一個同倫類**：「直接走過去」。真正的空間不確定性已經呈現在可達範圍帶上（D21 報告：17 步合計 281.125 m²、聯集 37.0 m²），只是不會變成第二條代表路線。

### 1.5 結論（三類）

| 類別 | 判定 | 說明 |
| --- | --- | --- |
| 地圖幾何只容許一種 | **主因之一** | 兩端點可直視，預算內沒有能繞的障礙物 |
| 盲區太短 | **主因之一（和上一項一起）** | 7.79 m 的預算不夠繞任何障礙物（粗估最短 13.1 m）。若盲區夠長，同樣兩端點也可能出現繞桌路線 |
| K1 規則造成 | **次要，屬設計而非錯誤** | 代表路線定義為「拉直後的路線」（契約 §4.5–4.7），所以同一同倫類內的「繞大弧」不會成為獨立候選。間距略過**不是**原因（§1.3 已證） |

供複核的位置（**未修改**；行號依 blob `1f0f674`，74c6ace 對應行號放在括號內）：

1. `engine.py:1570–1575`（74c6ace：1689–1694）：`_settle_anchors(_string_pull(...))` 之後以折線 key 去重。重複嘗試不計入 `rejected_counts` 或 trace，因此回應看起來像「沒有任何候選被拒」。**建議（不在本任務）**：在 `ROUTE_POOL_BUILT` trace 加一個 `duplicates_collapsed` 計數（這次是 531），讓「為什麼只有 1 條」可以直接從回應讀出。這會改變真實 run 的輸出 hash，C4b 的 K1 複本也要同步，需另開任務並和 Codex 協調。
2. `engine.py:1412–1443`（74c6ace：1531–）`_string_pull`：via 格在可直視時會被拉掉，這是「代表路線＝拉直路線」的設計來源。
3. `engine.py:1584–1593`（74c6ace：同一函式中對應段落）：間距略過（通過的路線用 `min_separation_m` buffer）。已驗證不是本案原因。

另外，#26 的 D19 更正已記錄：先前「3 條」來自 #46 之前 FRONT 區間 2.16 m 較長，不同錨點位置之間的距離超過 0.75 m。端點區間縮到 0.74 m 後，這個來源也消失了。

**對 K8 的啟示**：合成端點必須讓兩端**彼此不可直視**、中間隔著障礙物，而且盲區要長到能從障礙物兩側繞過，K1 才會產生多於 1 條代表路線。S1 就是照這個原則選的。

## 2. 共同設定（S1–S3）

- 地圖：同 §0 的 C7 person variant（SHA `53c37713…`），floor_z 0.4959475898742676 m。
- K1 設定：沿用 `office_person_blind_hypothesis_v1.json` 的全部數值（D2 速度 0–2.0 m/s、nominal 1.3 m/s、0.2 s 步長、body radius 0.25 m）。合成場景只新增一個 `scenes["synthetic-office-k8"]` 條目，內容複製 person 條目並加 `data_origin: "SYNTHETIC"`。**不針對結果調整任何參數**（D2 凍結規則）。
- 端點：`interval-observation v1`，`estimate_kind: POINT`，`pixel_sensitivity_m` 0.15 m（端點區為半徑 0.15 m 的圓），`contact_quality.status: PASS`，`provenance.gt_read: false`，`provenance.data_origin: SYNTHETIC`。端點只是**模擬感測器的輸出**；完整真值軌跡永遠不進 K1（§6）。
- 時間：合成時鐘 `SYNTHETIC_K8_5HZ`，t0 = 10.0 s（刻意不和真實 run 的 0–9.8 s 重疊，避免截圖或口頭說明時混淆）。
- 試跑中的 `scene_id` 是 `synthetic-office-k8`，鏡頭 id 是 `SYN_CAM_*`（不使用真實鏡頭 id，見 §7）。

障礙物位置（C7 person 地圖的洞，供下文參考）：桌子 hole 4 在 x 39.67–44.05、y 49.14–50.71；北側通道 y 50.71–51.34（寬 0.63 m）；南側通道 y 48.28–49.14（寬 0.86 m）。

## 3. 情境 S1：top-k 多假設

**設計**：起點和終點分別在同一張桌子（hole 4）的西側和東側，同一個 y，直線被桌子擋住，只能從北側或南側繞。

| 欄位 | 值 |
| --- | --- |
| 起點 | `SYN_CAM_A`，t = 10.0 s，POINT (38.60, 49.93)，r 0.15 m |
| 終點 | `SYN_CAM_B`，t = 16.0 s，POINT (45.20, 49.93)，r 0.15 m |
| 盲區 | 6.0 s（29 步，10.2–15.8 s），真實 run 的 1.67 倍 |
| top_k | 3 |
| 預期 | ≥2 條，北側與南側各一 |

**實際結果（K1 實跑）**：READY，k = 3。

| rank | 走法 | 長度 | 平均速度 | 和其他路線的最大間距 |
| --- | --- | --- | --- | --- |
| 1 | 桌北（route y 50.00–50.75） | 6.738 m | 1.12 m/s | 與 #2：1.75 m |
| 2 | 桌南（route y 49.00–49.86） | 6.783 m | 1.13 m/s | 與 #3：2.25 m |
| 3 | 桌北、繞較外側（y 50.00–51.25） | 7.383 m | 1.23 m/s | 與 #1：0.75 m（剛好等於門檻） |

trace：`ROUTE_POOL_BUILT` candidates 166、間距略過 642；`rejected_counts` speed 37、diversity 63；passing 129；`limits.hit` 為空。

盲區長度敏感度（同端點，只改終點時間）：

| 盲區 | k | #1／#2 | 平均速度 #1 | 備註 |
| --- | --- | --- | --- | --- |
| 4.0 s | 3 | 北／南 | 1.68 m/s | 接近上限 |
| 5.0 s | 3 | 北／南 | 1.35 m/s | #3 是南側外繞（與 #2 相距 0.82 m） |
| 6.0 s | 3 | 北／南 | 1.12 m/s | **建議值** |
| 8.0 s | 3 | 北／南 | 0.84 m/s | pool 達 `MAX_CANDIDATE_PATHS` 256 |

建議 6.0 s，理由：平均速度落在 nominal 1.3 m/s 以下的合理範圍，pool 沒有碰到上限，S3 也用同一組端點。展示時以 #1／#2 說明「桌子兩側兩種走法」；#3 和 #1 的間距剛好等於門檻，口頭上說成「北側的另一種變化」，不另外宣稱是第三種走法。

## 4. 情境 S2：跨鏡頭候選排除

**設計**：1 個 FRONT 端點，配 3 個合成 REAR 出現，對每一對逐一執行 K1（請求的 `candidate_ref` 欄位填候選 id）。身分一律 `UNCONFIRMED`。使用者已決定「第二人形干擾者」延到 11/01 之後，所以 S2 **只用合成候選**，不規劃任何真實干擾者資料。

| 候選 | REAR 位置 | 出現時間 | 盲區 | K1 實際結果 | 判定 |
| --- | --- | --- | --- | --- | --- |
| R1 | (45.20, 49.93) | 16.0 s | 6.0 s | READY，k 3（同 S1） | `REACHABLE` |
| R2 | (27.00, 40.00) | 16.0 s | 6.0 s | UNKNOWN `ENDPOINTS_UNREACHABLE`，`straight_line_m` 14.97 > 2.0 × 6.0 = 12.0 | `UNREACHABLE_UNDER_CONFIG` |
| R3 | (45.20, 49.93) | 13.2 s | 3.2 s | UNKNOWN `NO_HYPOTHESIS_PASSED_CHECKS`：可達界非空，36 條候選全部速度不通過 | `UNDETERMINED`（**不排除**） |

R3 的邊界（同一位置、不同時間）：13.0 s 是 `ENDPOINTS_UNREACHABLE`（直線 6.30 m > 6.0 m）；13.4 s 是 READY、k 2、平均 1.98 m/s；13.6 s 是 READY、k 2。這組可以拿來說明「同一個地點，太早出現就不可能是同一人」，以及判定在門檻附近的行為。

### 4.1 用現有 K1 判定可達／不可達的語意

| K1 回應 | S2 判定 | 理由 |
| --- | --- | --- |
| READY（k ≥ 1） | `REACHABLE` | 至少一條路線通過 speed／walkable／unseen 檢查 |
| UNKNOWN `ENDPOINTS_UNREACHABLE`（`straight_line_m` 或 `empty_at_s`） | `UNREACHABLE_UNDER_CONFIG` | 兩種都是下界證明：直線距離，或已經放寬（×1.0824 + slack）的測地可達界在某一步為空。結論有條件：在設定速度上限（D2）、這張地圖、這兩個端點區之下，不可能是同一個目標 |
| UNKNOWN `REACHABLE_SET_EMPTY` | `UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE` | 加上負證據後才變空；S2 沒用負證據，但語意要先定好 |
| UNKNOWN `NO_HYPOTHESIS_PASSED_CHECKS` | `UNDETERMINED` | 候選池是有上限的取樣，不是窮舉；沒找到通過的路線不等於證明走不到 |
| 其他 UNKNOWN（`ENDPOINT_UNUSABLE`、`SEARCH_BUDGET_EXHAUSTED`、`INTERVAL_TOO_LONG` 等） | `UNDETERMINED` | 證據或資源不足，不是可達性結論 |

畫面用語：`UNREACHABLE_UNDER_CONFIG` 說成「在設定的最高速度下走不到 → 排除此候選」，不說「不是同一人」以外的物理結論；`physical_authority` 仍是 `UNKNOWN`。

### 4.2 現有介面夠不夠？

逐對呼叫 `generate_blind_hypotheses` 加上 `candidate_ref`，是**現有能力**，S2 不改 K1 就能跑。缺的只有「把多個候選的結果整理成一張表」。**新增**（非現有能力）的最小純函式：

```python
# 新增：src/amidst/blind_hypothesis/candidate_screen.py
def screen_cross_camera_candidates(
    start: Mapping,                 # 同 K1 request["start"]
    candidates: Sequence[Mapping],  # 每筆：{"candidate_ref", "end"}，end 同 K1 request["end"]
    *, base_request: Mapping,       # session_ref、scene_id、top_k、negative_evidence
    config, config_sha256, floor_map, source_binding, visibility_index_ref=None,
) -> dict:
    # 回傳 {"schema_version": "workbench.candidate-screen.v1",
    #       "results": [{"candidate_ref", "verdict", "k1_status", "k1_reason",
    #                    "k1_response_sha256", "straight_line_m"|None,
    #                    "identity_verdict": "UNCONFIRMED"}...],
    #       "verdict_basis": "CONFIGURED_SPEED_RANGE_NOT_PROBABILITY",
    #       "output_sha256": ...}
```

這個函式只是迴圈與映射：不排序成機率、不挑「最可能是同一人」的候選，K1 回應原樣保留供檢視。

## 5. 情境 S3：負證據剪枝

**設計**：從 S1 的回應出發（不帶負證據），用 K5 的 append-only 重跑，依序加入兩筆合成負證據：

| 步驟 | 證據 | 可見地面（`visible_floor.polygons`） | 影格 |
| --- | --- | --- | --- |
| 0 | 無（= S1） | — | — |
| 1 | `negev:synthetic-k8-north`，`SYN_CAM_N`，`NO_DETECTION` | 矩形 x 39.0–44.8、y 50.3–51.6（涵蓋北側通道；與桌面重疊不影響） | 11.0–15.0 s 共 21 張 |
| 2 | 再加 `negev:synthetic-k8-south`，`SYN_CAM_S` | 矩形 x 39.0–44.8、y 48.0–49.4（南側通道） | 同上 |

**證據產生路徑（74c6ace 複跑）**：合成負證據不手寫成 K1 entry，而是組一個合成的 `workbench.frame-retrieval.v1` 回應，送進 K5 的 `negative_evidence_from_retrieval`，和真實畫面牆走同一條路徑。需要的輸入：

- `frame_evaluations[frame_ref]`：`frame_available`、`rgb_hash_verified`、`provenance_ok`、`perception_evaluated` 都是 `true`，`measurement_count: 0`，`detection_producer: {producer: "synthetic-k8", version: "v1", difference_threshold: 30, min_pixels: 28}`。
- `visibility_entries[visibility_ref]`：`method`、`floor_z_m`、`polygons`、`index_sha256`、`visibility_rule: "FOOT_AND_TORSO_PROBES_VISIBLE"`（D21），以及 `detectability.detector`，四個欄位（producer、version、`difference_threshold`、`min_pixels`）的值與型別都要和 `detection_producer` 相同。

`difference_threshold` 30 與 `min_pixels` 28 照抄 C5 D21 index 中 `rgb-mask-contact-v2` 的數值，用意是讓畫面牆顯示的參數有可比性；producer 名稱 `synthetic-k8` 讓它不會被誤認成真實偵測器的輸出。**負對照**：`detection_producer` 只帶 producer／version 時，21 張影格全部是 `UNKNOWN`／`DETECTOR_PARAMETERS_MISMATCH`，產生 0 筆候選；補上兩個參數後全部 `ELIGIBLE`，各產生 1 筆。轉出的 entry 中 `detection_producer` 只保留 `{producer, version}`，這是 K5 現行行為；K1 engine 只檢查 `producer` 欄位存在。

**實際結果（K1／K5 實跑，`previous_response_sha256` 鏈）**：

| 步驟 | status | 有效假設 | 本次剪掉 | 29 步可達面積合計 | 該證據時窗內面積（pruning_log） | `UNSEEN_MASK_APPLIED` 移除 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | READY | 3（北、南、北外繞） | — | 649.000 m² | — | 0 |
| 1 | READY | 3（全部在南側：6.783／7.484／7.822 m） | 2（#1 北、#3 北外繞；pruning ref 依版本而異：1f0f674 `pruning:0c27210d…`、74c6ace `pruning:9ee7695c…`） | 611.438 m²（−5.8%） | 28.030 → 26.241 m²（−6.4%） | 601 格·步 |
| 2 | READY | 3（改繞其他桌子：10.27／10.76／11.01 m，平均 1.71–1.83 m/s） | 3（步驟 1 的三條南側路線） | 574.500 m²（−11.5%，相對步驟 0） | 26.241 → 24.482 m² | 1192 格·步 |

展示重點：步驟 1 是「鏡頭看過北側通道、沒看到人 → 北側路線被剪掉」；步驟 2 再看過南側，剩下的假設被推到更遠、更快、接近 2.0 m/s 上限的繞行，可以接著說「如果再看一個畫面還是沒有，就可能整個可達集合變空」（`REACHABLE_SET_EMPTY`）。D19 的口徑仍然適用：講可達帶的收斂，路線條數只當作輔助。

### 5.1 為什麼不能用真實鏡頭的可見多邊形

真實 D21 可見地面（C5 index `7c464ec4…`，SOURCE_MESH_RAYCAST）在桌子區只涵蓋北側通道的 20%（FRONT）／21%（REAR），南側通道的 17%／24%；依 body radius 0.25 m 侵蝕後只剩 8–17%。桌子遮擋了大部分通道，所以 S3 需要合成的可見地面。

### 5.2 方法標記問題（必須處理）

K1 目前只接受 `visible_floor.method == "SOURCE_MESH_RAYCAST"`；K5 的 `negative_evidence_from_retrieval` 也要求 visibility entry 與影格 `footprint_method` 都是這個值（否則是 `FOOTPRINT_NOT_SOURCE_MESH_RAYCAST`）。試跑時合成多邊形在**記憶體內**暫時填了這個值，只為了驗證可行性；**正式 fixture 不可以這樣標**，因為手畫的矩形不是光線投射結果。兩種做法：

- **(a) 建議，Claude**：K1 新增允許值 `SYNTHETIC_DECLARED_FOOTPRINT`，只在設定的 scene 條目有 `data_origin: "SYNTHETIC"` 時接受，其他場景一律拒絕（`VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST` 不變）。K5 的 `retrieval_evidence.py` 也要以同樣條件接受這個 method；`DETECTOR_PARAMETERS_MISMATCH` 與 D21 `visibility_rule` 的檢查不放寬。回應的 `negative_evidence_applied` 與 trace 保留這個 method。改動很小，真實場景行為不變，但 K1 檔案改了，C4b 的 K1 複本要依同步清單更新（只有內容變動）。
- **(b) 備選，Codex**：從 Office 來源 mesh 為虛擬鏡頭做光線投射，得到誠實的 SOURCE_MESH_RAYCAST 多邊形。需要相機幾何與 raycast 工具，屬 Codex 範圍，不必渲染，但工作量與時程不確定（UNKNOWN）。

## 6. 合成真值與評估（兼 RQ2）

### 6.1 原則（D1）

- 合成真值軌跡**只用於評估**，絕不進 K1／K5 輸入。
- 進入 K1 的只有「模擬感測器輸出」：(i) 端點觀測 = 真值在 t0／t1 的位置，加上固定 seed 的雜訊（落在 `pixel_sensitivity_m` 內）；(ii) 負證據 = 合成鏡頭在某影格**沒有**看到真值（body disc 不和可見多邊形相交）時，產生 `NO_DETECTION`。看得到真值的影格**不**產生負證據（正向觀測不在 K8 範圍）。
- 自動測試必須檢查：K1 request 只含契約欄位（K1 本身會拒收多餘欄位），而且產生器寫出的 fixture 中，真值檔和推論輸入檔分開、hash 分開。

### 6.2 產生器（設計）

- 輸入：C7 地圖、起訖端點、盲區長度、seed。不使用 K1 的 lattice，避免拿 K1 自己的格網評估 K1。
- 路線：1–2 個 seed 隨機 via 點（範圍 x 36–49、y 44–56），各段直線必須完全在地圖內（`covers`）。正式版可以改用獨立的細格網（例如 0.1 m）Dijkstra，產生沿牆繞行的路線。
- 速度：6 段分段常數速度，權重取 U(0.5, 1.5) 後正規化到盲區長度；任何一段 > 2.0 m/s 就拒絕重抽（符合 D2／D12）。可選擇加停留段（速度 0）。
- 輸出：每 0.2 s 一個真值點，加上 seed、產生器版本、地圖 hash。

### 6.3 評估指標

| 指標 | 定義 |
| --- | --- |
| `coverage_strict` | 真值點落在該時刻可達帶 cell 方格內的比例（每步、每條真值） |
| `coverage_wall_tol` | 同上，但容許距最近 cell 方格 ≤ 0.177 m（半對角線）且距地圖邊界 ≤ 0.125 m 的點；用來分開「格網沒涵蓋貼牆帶」和真正的漏包 |
| `false_prune` | 剪枝前有涵蓋、剪枝後沒有涵蓋的真值步數；應為 0 |
| `nearest_hypothesis_sep` | 真值和最近代表路線的最大逐時距離（輔助，不是正確率） |
| 收斂 | 可達面積合計前後差（同 S3） |

### 6.4 可行性試跑（S1 端點、6.0 s、50 個 seed）

- 50 條真值，最大分段速度 1.97 m/s。
- `coverage_strict`：44 條 29/29 全部涵蓋；6 條各有 1–2 步在帶外，合計 8/1450 步（0.55%）。
- 那 8 個點都距地圖邊界（桌緣）0.012–0.083 m，超出最近 cell 方格 0.01–0.05 m，屬於 lattice 沒涵蓋的貼牆帶（和 K1 trace `SAMPLE_REGION_CONSISTENCY.wall_strip_exempt` 處理的是同類現象），不是速度或剪枝問題。改用 `coverage_wall_tol` 就全部涵蓋。
- 剪枝（北側合成鏡頭，只在真值不可見的影格產生 `NO_DETECTION`）：38 條真值有一致的負證據影格，剪枝後涵蓋情況和剪枝前完全相同，`false_prune` = 0；另外 12 條真值在整個時窗都在北側鏡頭可見範圍內，所以不產生負證據。
- 這次只是驗證方法可行；正式 RQ2 數字由 K8d 產生並記錄。

## 7. 標示與隔離

| 層面 | 規則 |
| --- | --- |
| 資料 provenance | 每個 fixture 與回應都帶 `data_origin: "SYNTHETIC"`、`generator`（腳本路徑 + git blob）、`seed`、`map_sha256`、`config_sha256`、K1／K5 engine blob |
| 場景 id | `synthetic-office-k8`；`run_ref` `synthetic:k8-office-v1`；clock `SYNTHETIC_K8_5HZ`。不與 `blender-office-person` 共用 scene、run、clock、`source_sha256`／`safe_inputs_sha256`（合成資料填 `SYNTHETIC_NONE`，不得借用真實 hash） |
| 鏡頭 id | `SYN_CAM_*`。不使用真實鏡頭 id，避免和真實影格、C5 index 對上 |
| 觀測與影格 ref | 前綴 `synthetic-observation:`、`synthetic-frame:`、`negev:synthetic-` |
| 檔案位置 | 產生器在 `src/amidst/synthetic/`、fixture 在 `frontend/workbench/fixtures/k8-synthetic-*.json`、真值在 `data/evaluation/k8_synthetic/`（只給評估工具讀） |
| 後端 | 不註冊進 preset、ReviewStore 或 C4b 快取；`start_office_demo.py` 不載入 |
| 前端 | 獨立的 Demo 步驟組 `synthetic`；切入時全畫面浮水印「SYNTHETIC 合成資料」（沿用 K6 MOCK 浮水印機制，換文字與顏色）；圖例加「合成端點／合成鏡頭可見範圍」；2D 鏡頭格顯示「SYNTHETIC：無影像（未渲染）」佔位；狀態列顯示 scene id。真值只在評估圖表中出現，預設不畫在推論圖層上 |
| 口頭說法 | 「在同一張 Office 地圖上，用合成端點展示系統能力」；不說「系統在 Office 找到了…」 |

## 8. 資料交付方式

**建議：靜態 fixture**，由純函式腳本產生，可重現。

- `scripts/k8_generate_synthetic_fixture.py` 呼叫 `src/amidst/synthetic/k8_office.py`（產生端點與證據）→ K1／K5（S1、S3 的回應鏈）→ `candidate_screen`（S2）→ 寫出 `frontend/workbench/fixtures/k8-synthetic-office.fixture.json`，內含三個情境的完整 K1／K5 回應、C7 地圖多邊形（2D 底圖用）與 provenance。
- 理由：
  1. 不需要改後端或 API 契約，也不需要 Codex。
  2. 確定性：同一 commit、同一 seed，產生相同的 `output_sha256`（§0 已驗證）。測試可以重跑產生器比對 hash。
  3. Demo 彩排與備援錄影可以離線跑，不依賴 live service。
  4. 和真實 scene 的 registry、快取、ReviewStore 天然隔離。
  5. K4 已經有相同模式（`frontend/workbench/fixtures/generate_blind_hypothesis_fixtures.py` → `blind-hypothesis.fixture.json`），前端可以沿用 K4 的路徑束與範圍帶 renderer。
- API 方案（後端註冊合成 scene）延後；只有在 Demo 需要「現場輸入新的合成端點」時才考慮，需要 Codex。

### 8.1 步驟編排建議

D22 移除原步驟 5 後，建議：

| 新步驟 | key | 內容 | 資料 |
| --- | --- | --- | --- |
| 1 | `play_both` | 同步播放 | 真實 |
| 2 | `front_select` | 選定目標 | 真實 |
| 3 | `blind_bundle` | 盲區路徑（NONE，1 條 + 範圍帶） | 真實 |
| 4 | `rear_reappear` | 後鏡再現 | 真實 |
| 5 | `suggested_wall` | 建議檢視 + 套用 BASELINE（D19：「這段影格沒有提供足夠的排除證據」） | 真實 |
| 6 | `synthetic_topk` | S1：桌子兩側兩種走法 | **SYNTHETIC** |
| 7 | `synthetic_candidates` | S2：三個後鏡候選，可達／排除／無法判定 | **SYNTHETIC** |
| 8 | `synthetic_pruning` | S3：北側沒看到 → 剪北；再加南側 → 剩遠繞 | **SYNTHETIC** |
| 9 | `negative_case` | 負例 | 真實（現行步驟 7） |

這和任務原本的建議（把合成段直接放進空出來的步驟 5）**不同**，理由：D19 的「先不套用（步驟 3）→ 再套用（畫面牆）」是同一段真實資料的連續敘事，中間插入合成段會切換場景兩次，觀眾容易把合成數字和真實數字混在一起。把畫面牆往前移到 5、合成段整段接在 6–8，只切換一次，浮水印也只出現一次。如果協調者偏好原案（合成段在 5、畫面牆在 6），K8e 只要改步驟檔，不影響 fixture。

另外，`origin/claude/k6-demo-mode` @ `160b21b` 的 `demo-steps.office.json` 仍然有原步驟 5 `candidate_switch`（`requires: cross_camera_result`），D22 的移除還沒落到該分支，K8e 要和這個改動一起排。

## 9. 實作任務拆分

| 任務 | 檔案 | 測試 | 負責 | 模型／effort | 工作量 | 依賴與先後 |
| --- | --- | --- | --- | --- | --- | --- |
| **K8a** K1／K5 合成可見性 method | 以 #48（74c6ace）為基底：`src/amidst/blind_hypothesis/engine.py`（只動 `_negative_evidence` 與 config 解析）、`retrieval_evidence.py`（footprint method 條件）、`configs/` 合成設定檔（新檔） | `tests/blind_hypothesis/` 新增：合成 method 只在 SYNTHETIC scene 接受；真實 scene 拒收；`DETECTOR_PARAMETERS_MISMATCH` 對合成證據仍然生效；真實 run 輸出 hash 不變 | Claude（K1 owner）；Codex 只需依同步清單更新 C4b 複本 | Opus／high（演算法模組、契約影響） | 0.5 日 | 先於 K8b。若選 §5.2(b)，改為 Codex 任務 |
| **K8b** 合成產生器與 fixture | `src/amidst/synthetic/__init__.py`、`src/amidst/synthetic/k8_office.py`、`scripts/k8_generate_synthetic_fixture.py`、`frontend/workbench/fixtures/k8-synthetic-office.fixture.json` | `tests/synthetic/test_k8_office.py`：重跑 hash 相同；所有輸出帶 SYNTHETIC；S1 k ≥ 2、S2 三種判定、S3 剪掉北側；S3 證據經 `negative_evidence_from_retrieval` 產生，且 `detection_producer` 帶 `difference_threshold`／`min_pixels`；真值不出現在任何 K1 request | Claude | Sonnet／medium | 1 日 | 需 K8a、K8c |
| **K8c** S2 候選篩選純函式（新增） | `src/amidst/blind_hypothesis/candidate_screen.py` | `tests/blind_hypothesis/test_candidate_screen.py`：§4.1 映射表逐列；identity 恆為 UNCONFIRMED | Claude | Sonnet／medium（語意已在 §4.1 定好；完成後由 Opus 複核） | 0.5 日 | 可和 K8a 平行 |
| **K8d** RQ2 評估工具與圖表 | `src/amidst/evaluation/k8_rq2.py`、`scripts/k8_rq2_report.py`、`docs/engineering/K8_RQ2_RESULTS.md`、圖檔 | `tests/evaluation/test_k8_rq2.py`：固定 seed 結果；`false_prune` 計算；真值與推論輸入隔離 | Claude | Sonnet／medium | 1 日 | 需 K8b。計畫 §7 列為最先可砍；若時間不夠，至少保留 `coverage`／`false_prune` 兩個數字 |
| **K8e** 前端合成步驟組 | `frontend/workbench/synthetic-demo.mjs`（新）、`demo-steps.office.json`、`demo-mode.mjs`（浮水印文字與步驟組）、`src/amidst/workbench/service.py` 靜態檔白名單一行 | `synthetic-demo.test.mjs`、`demo-mode.test.mjs`、`static-assets.test.mjs` | Claude | Sonnet／medium（沿用 K4 renderer；若要新的 3D 元件改為 high） | 1.5 日 | 需 K8b fixture、K4（#35）路徑束與範圍帶、K6（#38）步驟組；和 D22 renumber、K5 畫面牆的步驟調整同一個 PR 或緊接著做 |
| **K8f** 瀏覽器驗收與截圖 | `docs/agents/` 驗收紀錄 | 瀏覽器逐步截圖（步驟 6–8 有浮水印、圖例、無真實 hash） | Claude | Sonnet／medium | 0.5 日 | 最後；CP3（10/29）前 |
| Demo 腳本 | `docs/agents/OFFICE_DEMO_SCRIPT.md`（#38） | — | Claude（K6） | Sonnet／medium | 0.25 日 | 和 K8e 一起 |

**和 A2、A4、K5 畫面牆的先後**：

- 本 session 找不到 A2、A4 的正式定義（repo 文件、#22／#23／#26 留言、notes 都沒有；只有 K6 commit 用到 A1、A3）。依「彩排前還缺什麼」清單的順序推測，A2 = K3 後半（從 `target_reconstruction` 取 `selection.ground_estimate`），A4 = 選定目標高亮（步驟 2）。這個對應是 **UNKNOWN**，請協調者確認。在這個推測下，兩者都只動真實步驟，和 K8 沒有資料相依；只有在 `app.mjs`／`demo-mode.mjs` 有合併衝突的風險，建議 K8e 排在它們之後。
- K5 畫面牆（真實步驟 5，接 `POST /api/frame_retrieval`）和 K8 沒有資料相依，但兩者都改 `demo-steps.office.json` 的步驟編號，建議畫面牆先落地，K8e 再接上合成步驟 6–8。
- K8a／K8c／K8b／K8d 都是後端純函式，不碰前端，可以和 A2、A4、畫面牆平行。

建議時程：K8a＋K8c（10/19–20）→ K8b（10/21）→ CP2（10/24）只展示 fixture 與數字 → K8e（10/25–27）→ K8f（10/28）→ CP3 凍結（10/29）。K8d 依剩餘時間決定。

## 10. 風險與 UNKNOWN

1. **合成被誤認為真實**：靠 §7 的浮水印、獨立 scene id、不借真實 hash 降低風險。驗收時要檢查截圖中步驟 6–8 都有浮水印。
2. **method 標記**：在 K8a 完成前，任何合成負證據都不能進 repo（試跑只在記憶體中）。
3. **K1 複本同步**：K8a 改到 K1，C4b 的 K1 複本需要同步（#44 模式）；真實 run 的輸出 hash 不應改變，K8a 的測試要鎖住這一點。
4. **假設 ref 會變**：本文件的 `hyp:` ref 與 `output_sha256` 來自試跑的 binding 與設定 hash；正式 fixture 的 provenance 不同，ref 會改變。條數、長度、剪枝結構應保持不變，K8b 的測試要鎖住結構而不是 ref。
5. **S1 #3 剛好在門檻上**（0.75 m）：設定或拉直細節稍有變動，#3 可能消失或換成南側外繞，所以展示只依賴 #1／#2。
6. **S2 只有速度式排除**：在 9–11 m 環帶內抽 36 個點，沒有找到「直線可達但地圖繞路後不可達」的位置（Office 地圖很開放）。所以 S2 展示的是速度上限下的排除，不宣稱「地圖阻擋」。
7. **貼牆帶涵蓋**：§6.4 的 0.55% 未涵蓋點是 lattice 的貼牆帶；RQ2 必須同時報告 strict 與 wall_tol，不能只挑好看的。
8. **前端 3D 底圖**：合成步驟沒有影像，3D 只能畫 C7 地圖多邊形；如果要畫 Office mesh 當背景，必須確認不會載入真實 run 的觀測或標記（UNKNOWN，K8e 時確認）。
9. **D23 第 3 點**：Codex 已唯讀確認沒有現成渲染片段同時符合「盲區夠長、≥2 種走法、兩端接地可用」，舊 baseline run 的 FRONT 是 `AMBIGUOUS_MERGE`。使用者已決定第二人形干擾者延到 11/01 之後，所以 S1–S3 全部使用合成端點與合成候選。
13. **K1 版本漂移**：#48 合併前後的 K1（1f0f674 → 74c6ace）回應欄位不同，`hyp:` ref 相同，但 `output_sha256` 與 pruning ref 不同。K8b 應以合併後的 K1 產生 fixture，並在 provenance 記錄 engine blob。
10. **A2／A4 定義**：UNKNOWN（見 §9）。
11. **候選池上限**：S1 盲區 8.0 s 時 pool 已碰到 256 上限；如果將來加長盲區，`limits.hit` 會出現 `MAX_CANDIDATE_PATHS`，畫面要照實顯示。
12. **去重不透明**（§1.5 第 1 點）：「為什麼只有 1 條」目前無法只從回應讀出；建議另開 K1 小任務，加 `duplicates_collapsed` 計數。
