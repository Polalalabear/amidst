# r004 4 人場景產製驗收關卡 v1（D206）

- 狀態：**規範性（normative）**。對象：Codex，issue #516。測試：[`tests/q1q5/test_r004_v2_516_gates.py`](../../tests/q1q5/test_r004_v2_516_gates.py)。
- 作者／Model / effort：Claude Code，Sonnet 5.5 / medium。形式比照 [`AGENT_EVAL_TOOLCHAIN_GATES_V1.md`](AGENT_EVAL_TOOLCHAIN_GATES_V1.md)（#518）。
- 依據：[情境卡 v2](../evaluation/R004_A4B4_SCENARIO_CARDS_V2_4ACTOR.md)（D198、D203、D204）、[劇本草稿](../evaluation/R004_A4B4_SCENARIO_V2_4ACTOR_DRAFT.json)、[`check_actor_clearance.py`](../../scripts/design/check_actor_clearance.py)。

## 完成條件

- **可行性階段（#516 步驟 1，已授權，不渲染）：**G1 的 8 個測試全部由 xfail 轉 PASS，**並移除 `G1` 標記**，CI `checks` 綠燈。
- **渲染階段（需使用者另外授權）：**G1 + G2 的 12 個測試全部轉 PASS 並移除標記，CI 綠燈。
- 不要改斷言。覺得斷言或本契約有誤，在 #516 留言，由 Claude 改。strict xfail：通過但標記還在時 CI 會失敗，所以一定要同時移除標記。
- Codex 開 PR 後，在 #516 留言並標 `review:requested`，Claude 會主動審查。PR base 是 `main`（D200），只用 merge commit。

## 共同規則

1. 檔案不存在時，關卡是 xfail（不是 error）。交件檔放在下列固定路徑；改路徑要先在 #516 留言。
2. JSON 欄位名稱避開 `agent_decision.FORBIDDEN_KEYS`（`path`、`file`、`actor`、`scenario` 等）；G2 的 manifest 整份會被掃描。本契約用 `relative_path`。報告內的 `actor_id` 只出現在 G1（`spawn_points`），G1 不是決策端輸出，可以用。
3. 所有路徑都是**相對路徑**；LOCAL 檔相對於 `$AMIDST_ARTIFACTS`，不寫絕對的家目錄路徑。
4. G1 不渲染、不寫 `~/amidst/local/`、不存 `.blend`、不讀 GT；`boundary` 欄位要如實填寫。
5. 路線有問題（穿模、出現點在畫面內）就回報 #516，**不要自己改路線或草稿**；路線改動由 Claude 改情境卡。

## G1 可行性報告（不渲染）

**檔案：** `docs/evaluation/R004_A4B4_V2_FEASIBILITY_REPORT.json`（#516 沒有指定路徑，本契約定在這裡；已在 #516 留言）。`schema` = `amidst.r004-v2-feasibility.v1`。

| 欄位 | 內容 | 關卡 |
| --- | --- | --- |
| `inputs[]` | 每個輸入一筆：`relative_path`、`git_sha`（40 hex）、`sha256`（64 hex）。至少含劇本草稿、檢查器、唯讀開啟的 `.blend`、正式 HSV 設定 | `test_g1_report_schema_and_provenance` |
| `geometry.<run_id>` | `floor_z_m`；`walls[]`、`furniture[]`：`segment_id`、2D `a`/`b`、`height_range_m` [lo, hi]；`doors[]`：`door_id`、`center_xy`、`normal_xy`、`width_m`、`geometry_status` = `MEASURED`、`source_sha256`。A4 要有 `R004_WEST_ENTRY`，B4 要有 `PORTAL_R101`。`run_id` = `A4-1-v2-4actor`、`B4-1-v2-4actor` | `test_g1_geometry_walls_furniture_doors_measured` |
| `clearance` | `verdict` = `PASS`、`walls_status` = `PASS`、`command`、`checker_git_sha`。測試會**自己重跑檢查器**：把 `geometry` 的牆＋家具塞進 `walls`、換上量到的門，兩個 run 都要 `PASS`，牆距不得是 `UNKNOWN`（草稿現在是 `UNKNOWN`，見自我測試） | `test_g1_clearance_unknown_becomes_pass_with_geometry` |
| `spawn_points.<run_id>[]` | 每個干擾者（A、B、C）的第一個和最後一個路點各一筆：`actor_id`、`kind`（`first`/`last`）、`xy`（必須和草稿路點一致）、`method` = `static_projection`、`cameras_checked`（A4：EXT_CAR、EXT_CLEAR、W1；B4：BRANCH、R101_IN、W1、W2、WIDE）、`outside_all_render_cameras` = `true`。看得到就回報，不要自己移 | `test_g1_spawn_points_outside_all_render_cameras` |
| `color` | `red_band_hue` [lo, hi]、`hsv_config_sha256`、`t_hue`、`b_by_camera[]`（每個 run×渲染鏡頭一筆：`run_id`、`camera_id`、`b_hue_measured`、`in_band`、`crop_ratio` = 0.3）、`a_in_band` = `true`、`c_in_band` = `false`。B 每一支鏡頭的色相都必須在紅色帶內（D204，含光線偏移） | `test_g1_b_stays_in_red_band_under_every_camera_light` |
| `ambiguity` | `unit` = `episode`、`color_variant` = `in_band`、`episodes.<run_id>[]`（`start_s`、`end_s`、`has_distractor`）、`total_episodes`。**兩個 run 合計 ≥ 5 段**，每段都有干擾者（D203）。用情境卡 §6 的方法（`estimate_plan_decision_points.py`）在量到的條件下重算 | `test_g1_ambiguity_episodes_at_least_five` |
| `render_cost` | `runs.<run_id>.render_seconds_estimate`、`disk_gib_estimate`；`free_gib_before`、`total_disk_gib_estimate`、`includes_frames`。`free_gib_before − total_disk_gib_estimate` 必須 ≥ 8（停止線）；不夠就在 #516 留言，不渲染 | `test_g1_render_cost_and_disk_estimate` |
| `actor_cloning` | `feasible`（true/false）；true 時要有 `materials`（A、B、C）和 `shared_animation` | `test_g1_actor_cloning_and_boundary` |
| `boundary` | `rendered`、`wrote_local_dir`、`blend_saved`、`gt_read` 全為 `false` | 同上 |

若 B 在某支鏡頭被光線推出紅色帶，`color` 關卡就不會過；這是設計上要擋的（情境卡 §6.4：餘裕為零）。回報 #516，由 Claude 決定調 B 的材質或重排路線。

## G2 渲染交付（需使用者另外授權）

**檔案：** `docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json`（要提交，依 AGENTS.md「Handoff documents go on GitHub」；原始影格等 artifact 留在 LOCAL）。`schema` = `amidst.r004-v2-bundle-manifest.v1`。

| 欄位 | 內容 |
| --- | --- |
| `local_root` | 字面值 `$AMIDST_ARTIFACTS` |
| `files[]` | 每個檔案：`relative_path`（相對於 `local_root`）、`sha256`、`size_bytes`。不得出現 `gt_private`、`scoring_private`、ground truth、renderer 軌跡、visibility、depth 之類的名稱 |
| `file_count`、`total_bytes` | 必須等於 `files` 的數量和 `size_bytes` 總和 |
| `receipt` | `gt_read` = `false`、`detector_weights_sha256`、`code_git_sha`（40 hex） |
| `runs.<run_id>` | `run_id_new`（新 run id，不是舊 r004 d124 run）、`detector` = `RT-DETR`、`detection_index_relative_path`（必須列在 `files`）、`cameras.<camera_id>.{frame_count, fps}`：鏡頭集合與 G1 相同；`fps` = 5；`frame_count` 為 250 或 251（A4，50 s）、210 或 211（B4，42 s） |
| `stage_inputs` | `detection_index`、`local_track`、`ranking`、`reconstruction` 四個階段各自讀的檔案清單（`relative_path`，都必須在 `files` 裡）。任何一個階段的輸入都不能含 GT 或 renderer 軌跡（GT 隔離，DEVELOPMENT_RULES） |

manifest 整份的鍵不得命中 `FORBIDDEN_KEYS`（唯一例外：`receipt.gt_read`）。

## 自我測試（一般 PASS）

測試檔裡用**自己造的**合格與不合格資料（假報告、假 manifest，沒有真實 GT、渲染或 Blender）證明關卡能分辨：合格資料通過；14 種報告缺陷與 14 種 manifest 缺陷（絕對路徑、錯 SHA、`ASSUMED` 門洞、牆距仍 UNKNOWN、出現點在畫面內、B 色相出帶、歧義 < 5、磁碟低於停止線、GT 名稱出現在階段輸入、…）各自被拒絕；牆穿過路線時重跑的檢查器回 `FAIL`；真實草稿目前是 `UNKNOWN`。
