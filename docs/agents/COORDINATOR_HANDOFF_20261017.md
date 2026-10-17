# 協調者交接：Office Demo（2026-10-17 晚）

> 給下一個協調者 session。上一份交接是 2026-10-16 晚的版本（使用者以訊息提供，未入庫）；本文件取代它。
> 進度類內容是 10/17 晚的快照；即時狀態以 GitHub issue／PR 為準。決策全文在 [CP1 #25](https://github.com/Polalalabear/amidst/issues/25) 與 [CP2 #26](https://github.com/Polalalabear/amidst/issues/26) 的留言。

## 1. 角色與工作方式

- 你是「協調者」：分派任務、記錄決策、寫 brief、讀回報、核對數字。**不自己動手做任務**：開分支、寫程式、審查、在 issue／PR 留言、改文件，一律交給子 session（Claude）或 Codex。例外：使用者明確要求協調者本人執行時（例如 10/17 完成 CP1 時，以 `gh pr merge --merge` 合併 #11、#32、#10）。
- 回覆一律用繁體中文。使用者寫「簡單回答／僅回答」時只回答，不動手。
- 模型分級照 `CLAUDE.md`：Opus 只用於複雜程式碼的複核與設計判斷；一般審查、實作用 Sonnet；張貼留言、提交給定文字用 Haiku。兩段式審查：Sonnet 全面審查，有疑點才交 Opus 只看疑點。
- 後續修正送回已有前因後果的 session（`SendMessage`），不要開新的。
- 每個子 session 的回報要核對：測試數字、commit SHA、和預期不符就讀 diff 或升一級。
- 決策一律記到 checkpoint issue（D 編號），並在相關 PR 留言通知 Codex。給 Codex 的指派由使用者轉貼；協調者提供可直接貼的文字。

## 2. 環境與分支

- repo：`/Users/polalabear/Developer/amidst-claude`，共用 checkout，**不可建 worktree**，同一時間只能有一個寫程式的 session。checkout 平常停在 `claude/k1-hypothesis`。
- 6 個不屬於我們的未追蹤檔永遠不要 stage、移動或刪除：`configs/dual_camera_straight_line_v1.json`、`docs/engineering/WORKBENCH_AUDITORIUM_GEOMETRY_AUDIT.md`、`scripts/audit_auditorium_geometry.py`、`scripts/audit_auditorium_source.py`、`scripts/render_dual_camera_validation.py`、`src/amidst/workbench/dual_camera_validation.py`。
- 資產 `/Users/polalabear/Developer/amidst/`（唯讀；Codex 也在這裡工作，不要在裡面跑 git）。`.local-worktrees/phase1-finalization` 是 launcher 的證據來源，只能讀。
- 整合分支 `claude/office-demo-visualization` 在 `dcb89f4`（CP1 合併後）。main 在 `519e874`，只在 CP4 由使用者授權更新。
- 合併一律 merge commit，不 squash、不 rebase。

## 3. 操作上的坑（實際遇到過）

- **由子 session 回報觸發的那一輪不能直接開 session**，只能用 `own_initiative` 做成卡片等使用者按。但可以 `SendMessage` 給既有 session。使用者自己傳訊息的那一輪才能用 `user_asked` 直接開。
- **只改文件的提交**：用暫存 `GIT_INDEX_FILE` 加 plumbing（`read-tree` → `hash-object -w` → `update-index --cacheinfo` → `write-tree` → `commit-tree` → `git push origin <sha>:refs/heads/<branch>`），不碰工作樹，可以和寫程式的 session 並行。
- **唯讀審查**：只用遠端 ref；測試在 scratchpad 用 `git archive` 匯出，Python 用 `PYTHONPATH=<匯出>/src /Users/polalabear/Developer/amidst-claude/.venv/bin/python`，先確認 import 路徑；需要 git 的話在匯出目錄 `git init -q`。前端測試把 `frontend/workbench/node_modules` symlink 到共用 checkout 的那份。
- **瀏覽器驗收**：用 `git merge-tree --write-tree` 或 scratchpad 內的 `git clone --no-checkout` 合成副本；啟動時要設 `PYTHONPATH=<副本>/src`，否則 `.venv` 會載入共用 checkout 的舊版 `amidst`。
- **後端靜態檔白名單**：`src/amidst/workbench/service.py` 的 `assets` 只提供列出的前端檔案，新模組沒加就 403，整個工作台停在「正在載入」。K4 已加防呆測試 `frontend/workbench/static-assets.test.mjs`。K4、K6、K3 後半各自在分支加了一行，合併時同一區塊會有小衝突。
- **堆疊 PR**：Claude 的前端與演算法 PR 多數是堆疊的（base 指向上一個 PR 的分支）。Codex 的 C4b（#44）把 K1／K5 的檔案「原樣複製」進後端並記 pin；K1／K5 一改，Codex 要依同步清單更新複製。
- **zsh**：在 `:` 前面的變數要寫成 `${VAR}`；`echo =====` 會被當成指令展開。

## 4. 決策摘要（全文見 #25、#26）

| D | 內容 |
| --- | --- |
| D1 | 可見範圍索引可用靜態來源幾何做射線測試；renderer 逐幀可見性、軌跡、深度禁止進推論 |
| D2 | 速度範圍是模擬設定，評估前凍結 |
| D3 | 地圖由來源網格推導（C7），標註只作交叉核對（K7） |
| D4–D6 | 渲染授權、人形代理 1.70 m／r 0.25 m、身體半徑逐 run |
| D7 | 端點不可用時可沿同 track 回溯 ≤1.0 s，要明確標示 |
| D8 | `AMBIGUOUS_MERGE` 在 11/01 前一律不可用 |
| D9–D13 | C7 地圖 10/22 前交、K7 不得據 GT 改地圖、座椅區 UNKNOWN（已由 D16 修訂）、速度 ≤2.0 m/s、兩線並行（已由 D14 取代） |
| **D14** | Demo 主軸選 Office；C6 延後到 Office 完成後，15 條路線不渲染 |
| **D15** | 禁止區是獨立政策圖層（不是障礙物）；路徑可經過，以 tier `RESTRICTED_POLICY` 標示；D3 的明確例外，只限使用者確認的禁止區（Office 西側 `OBSTACLE_1F_OFFICE_01/02`） |
| **D16** | 修訂 D11：來源網格能解析的座椅與講台視為障礙物，走道可走；無法解析的座位區才標 UNKNOWN |
| **D17** | R1：LOW_INCIDENCE-only 先用頭頂射線區間但不套 `OCCLUDER_BEHIND`；契約 v1.1 升級為 `FOOT_RAY_PIXEL_BAND`（已由 #46 實作） |
| **D18** | 人形 run 端點 FRONT 4.6 s → REAR 8.2 s，盲區 4.8–8.0 s，不做 D7；舊 run 維持 4.4 → 8.6 s |
| **D19（已更正）** | Demo 以「先不套用負證據、再套用」展示，**只講可達帶收斂，不講路線條數**（兩者都是 1 條）；收斂接近 0 就照實說明，畫面牆改講「告訴調查者該看哪些畫面」 |
| **D20** | IO-Q8：`MAX_SEGMENT_LENGTH_M = 8.0` 定案（工程設定） |
| **D21** | C5 負證據可見性收緊為 `FOOT_AND_TORSO_PROBES_VISIBLE`（腳＋腰都可見）＋可偵測性檢查（≥112 px）；any-probe 足跡改為 `suggestion_polygons` 只用於排序；負證據以影格去重 |

另有兩項 CP1 處理：#11、#32（`a4d93d0`）、#10（契約 v1 草稿）已核准並合併（`7af003a`、`d79b885`、`dcb89f4`）；#34 移出 CP1。

## 5. 關鍵數字（都已由子 session 獨立核對）

- 舊 Office run（2.9393 m 圓柱）：C4a 0 READY，區間 9.4–11.8 m（鏡頭高 3.29 m，射線近水平）。
- 人形 run：鏡頭高於地板 3.288／3.289 m、俯角約 23.3°。C4a v1.1：29 個 `FOOT_RAY_PIXEL_BAND`（0.73–1.19 m）、4 個頭頂射線（CONTACT_OCCLUDED）；4.6 s 端點 0.738 m，8.2 s 端點 2.49 m。
- C4b（v1.1 凍結，#50）：1 條假設、17 個時刻；不套用負證據 281.125 m² → 套用 255.75 m²（**−9.026%**）；沒有路徑被剪。舊的「3→1、−16.6%」是頭頂射線端點時代的歷史數字。
- C5 足跡（現行 any-probe 規則）：FRONT 205.4 m²、REAR 202.6 m²；D21 嚴格規則下的值 UNKNOWN，等 Codex 重跑。
- K7：Office 實體幾何 IoU 0.877（只比 `WALK_*`），依 D15 判 `SOURCE_DERIVED_VERIFIED`＋禁止區圖層；6 條已渲染路線 300 個取樣點 0 違規。

## 6. 開啟中的 PR（10/17 晚）

### Claude

| PR | 內容 | 分支 @ head | base | 檢查點 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| #31 | K3 場景預設、品質旗標 | `claude/k3-presets-ui` @ 74af12f | 整合 | CP2 | 審查、瀏覽器驗收通過 |
| #42 | K3 後半：接地區間顯示 | `claude/k3-interval-obs` @ a8ad4aa | #31 | CP2 | 206 測試通過；白名單已補；瀏覽器未驗 |
| #33 | K1 盲區假設 | `claude/k1-hypothesis` @ 7c01522 | 整合 | CP2 | Opus 複核通過；薄牆尖端已知限制入契約 §12.4 |
| #36 | K5 剪枝重跑、檢索轉負證據 | `claude/k5-pruning` @ 726e390 | #33 | CP3 | 審查修正完成，113 測試 |
| #48 | K1 禁止區（D15）＋以影格去重（D21） | `claude/k1-restricted` @ 9470611 | #36 | CP2 | 175 測試；D15 部分已審查通過，D21 部分（`9470611`）**尚未審查** |
| #35 | K4 假設路徑束、禁止區標示、接 C4b API | `claude/k4-hypothesis-bands` @ 7a7f93e | 整合（疊在 K3 舊 head 8331e86） | CP3 | 尚未支援 D19 的兩次請求 |
| #38 | K6 Demo 模式、步驟組、驗收紀錄、Demo 腳本 | `claude/k6-demo-mode` @ 5f0df84 | #35 | CP3 | 瀏覽器驗收 D、G 通過；人形場景已接上 |
| #41 | K7 地圖驗證 | `claude/k7-map-verify` @ 1ef9bc9 | 整合 | CP2 | 含 §9 使用者決定 |
| #45 | K0 契約 v1.1（R1、D15–D21、K5 修訂） | `claude/contracts-v1-1` @ ed64070 | 整合 | CP2 | Codex 已逐條確認；D21 條文已補 |
| #39 | 問答文件 | `claude/office-demo-qa` @ 64c7992 | 整合 | — | 純文件 |

### Codex

| PR | 內容 | head | base | 檢查點 | 審查 |
| --- | --- | --- | --- | --- | --- |
| #37 | C4a 混合估計（含 D17） | 099513e | 整合 | CP2 | 通過 |
| #43 | 人形 preset／fixture（`blender-office-person`） | 7836765 | #37 | CP2 | 通過 |
| #44 | C4b 盲區假設 API | 0942f5a | #43 | CP2 | 通過 |
| #46 | C4a v1.1 `FOOT_RAY_PIXEL_BAND` | a6ce40c | #44 | CP2 | 通過（手算逐位元吻合） |
| #47 | C5 索引、檢索 API、真實負證據 | 6bafe04 | #46 | CP3 | 通過；D21 修改待實作 |
| #50 | Demo 啟動器、人形 readiness、D19 三模式、v1.1 凍結 | cd6c854 | #47 | CP3 | 通過 |
| #40 | C7 來源地圖、禁止區圖層 | a69e63f 之後 | 整合 | CP2 | 通過；文件衝突已解 |
| #51 | C3b 後續 | 5c72fe7 | 整合 | — | 通過 |
| #34 | C6（延後，D14） | 9937135 | 整合 | — | 不合併 |

追蹤 issue：#49（逐鏡頭腳點隱藏區 mask，未實作，低優先）。

## 7. 進行中（交接時）

- **端到端瀏覽器驗收**（已完成，見第 12 節；Sonnet，唯讀）：session `local_a640571a-7bfb-490b-8c5e-e78cd3a2090d`。把 Codex 堆疊（頂端 #50）與 Claude 兩條前端堆疊合成副本，用人形場景驗 A–G，並列出「離可以彩排 Demo 還缺什麼」。**使用者要求：拿到結果後整理一份「彩排前還缺什麼」清單。**
- **Codex**：依 D21 收緊 C5 規則（規格在 #47 協調者留言）；K1 同步（依 #48 的同步清單，含 `applied_frame_keys`）。C6 暫停。

## 8. Claude 待辦（依優先順序；寫入類一次一個）

1. （已完成，見第 12 節）讀端到端驗收結果，整理「彩排前還缺什麼」清單給使用者。
2. 審查 #48 的 D21 部分（`cbe5731..9470611`，Sonnet，唯讀）。
3. **K4／K6 支援 D19**：同一觀測先送 `negative_evidence_mode: "NONE"`，再送 `"BASELINE"`（可帶 NONE 回應的 `output_sha256` 作 `previous_response_sha256`）；顯示兩次的可達面積（`blind_hypotheses.reachable_regions[].area_m2`）與差異。對應 K6 步驟 3 與步驟 6。
4. **選定目標高亮**（Demo 步驟 2）：工作台目前沒有「選取一筆觀測」的機制；K6 只驗證觀測存在。brief 草稿見 10/17 的卡片（已撤下）：`state.selectedObservationRef`、2D／3D 高亮、檢視面板、身分 UNCONFIRMED、選取只影響畫法。
5. **K5 畫面牆**：接 C5 的 `POST /api/frame_retrieval`（請求 `query_kind: TIME_RANGE | HYPOTHESIS`、回應 `results[].windows[].frames[]`、`frame_outcomes`、`negative_evidence_candidates`、`stats`）；依 D21 只用 `polygons` 當負證據、`suggestion_polygons` 排序。
6. **CP2 合併準備**：依第 9 節順序，先處理 K3（#31／#42）與 K4（#35）在 `cross-camera.mjs`、`scene.mjs`、`frame-query.test.mjs`、`workbench-layout.test.mjs` 的衝突，以及 `service.py` 白名單衝突。合併需使用者在 #26 寫 APPROVED。
7. 報告研究段視覺素材（RQ1 資料、可達帶收斂前後）；Demo 腳本定稿（`docs/agents/OFFICE_DEMO_SCRIPT.md`，在 #38）；備援錄影（10/31 前）。
8. 低優先：RQ2 評估工具（合成路線；依計畫 §7 最先被砍）；問答文件 #39 補新內容。

## 9. 合併順序建議（CP2／CP3，需使用者核准）

- CP2：#51 → #45 → #33 → #36 → #48 → #31 → #42 → #41 → #40 → #37 → #43 → #44 → #46。
  - #44 內含 K1／K5 的複製檔；只要 Codex 已依 #48 同步，內容相同的 add/add 會乾淨合併。合併前用 `git merge-tree` 逐一確認。
- CP3：#47 → #50 → #35 → #38（K4／K6 前需先解 K3 衝突與白名單衝突）。
- #34（C6）不合併；#39 隨時可合（純文件）。

## 10. 使用者待決或待處理

- 看端到端驗收結果與「彩排前還缺什麼」清單後，決定彩排日期。
- CP2（目標 10/24）在 #26 核准；CP3（10/29 凍結）。
- D21 收緊後若收斂接近 0，依 D19 改講法（不需新決策，但要確認 Demo 腳本）。

## 11. 子 session 參考（可用 SendMessage 續用）

| 用途 | session |
| --- | --- |
| K4 前端 | `local_a54e508e-ea90-4522-8146-24c6b646cafd` |
| K6 Demo 模式 | `local_874a317b-315b-48e2-a5cb-a7f973808be8` |
| K5／K1 演算法（#36、#48） | `local_bfdf4160-ec23-4171-818c-6a42c482fae3` |
| K3 後半（#42） | `local_db6c1cb4-6cdc-4371-89f8-1012654690b7` |
| 契約 v1.1（#45） | `local_6ec0e77e-57bc-4209-a574-f7dcd0a1ac67` |
| 瀏覽器驗收（K6） | `local_cfa64196-cb44-42eb-9701-8b08d04a0ad5` |
| 張貼留言（Haiku） | `local_cd0e8831-02f8-4424-ac03-6be7b4f4cc6a` |
| 端到端驗收（已完成，見第 12 節） | `local_a640571a-7bfb-490b-8c5e-e78cd3a2090d` |

## 12. 第一次真實資料端到端驗收結果（2026-10-17 晚）

session `local_a640571a-7bfb-490b-8c5e-e78cd3a2090d`（Sonnet，唯讀）。合成方式：從 `origin/codex/office-demo-review-followup`（#50）依序合 K6（#38）、K3 後半（#42）、K4 head（#35 @ 7a7f93e）。**注意：K6 的堆疊不含 K4 最新的 3 個 commit**（ced1a12 白名單、3276709 D15 標示、7a7f93e API 接線），合成時要另外合 K4 head。衝突集中在 `service.py` 白名單、`cross-camera.mjs`、`scene.mjs`、`app.mjs` 與兩個測試檔，兩邊功能都保留即可；合完 `scene.mjs` 出現重複的 import，3D 載入失敗，刪掉一行後修好。合成後前端測試 337/337 通過；`PERSON_DEMO_READINESS=READY`。

| 項目 | 結果 |
| --- | --- |
| A 場景選單（含 `blender-office-person`） | 通過 |
| B 兩鏡頭＋3D 同步、盲區不畫位置 | 部分：時間同步正確，但人形場景 3D 沒有任何觀測點（33 筆 `world_position` 都是 MISSING，接地區間又沒接上，見 C） |
| C 接地區間（4.6 s 0.738 m、8.2 s 2.49 m） | API 正確；**UI 沒顯示**：K3 後半只從物理審查樣本讀 `ground_estimate`，人形場景的物理審查是 `NOT_MATERIALIZED_FOR_RUN`，`target_reconstruction` 回應裡的 `selection.ground_estimate` 沒人讀 |
| D 盲區假設路徑束 | 通過（有條件）：要手動按「盲區假設路徑束」；1 條假設、玫紅帶、外層 UNKNOWN／巢狀 READY 說明都正確 |
| E Demo 步驟 | 部分：步驟跳轉的時間與鏡頭正確；**K6 bug**：`app.mjs` 的 `getState` 沒傳 `humanoidSceneId`，所有人形步驟都顯示「人形場景未載入」 |
| F D19 API | 通過：NONE 281.125 m² → BASELINE 255.75 m²（−9.026%），與 #50 一致 |
| G console 與效能 | 通過（修好合成錯誤後無錯誤；頁面載入約 0.1 s，切場景與檢索 1–3 s） |

### 彩排前還缺什麼（依優先順序）

**Claude**
1. K6：修 `getState` 傳入 `humanoidSceneId`（`app.mjs` 約 1420 行、`demo-mode.mjs:20`）；步驟 3 自動呼叫或預先載入 `target_reconstruction`，不要靠手動按鈕。
2. K3 後半：改為也從 `target_reconstruction` 回應的 `selection.ground_estimate` 取接地區間，人形場景才看得到 4.6 s／8.2 s 的區間與 basis（同時解決 B）。
3. K4／K6：支援 D19 的兩次請求（`negative_evidence_mode: NONE` → `BASELINE`），顯示可達面積前後與差異。
4. 選定目標高亮（步驟 2）。
5. K5 畫面牆（步驟 6；接 `POST /api/frame_retrieval`，依 D21 只用 `polygons` 當負證據）。
6. 防呆：`static-assets.test.mjs` 對所有 `.mjs` 加 `node --check`，抓合併造成的重複 import。
7. 小瑕疵：「假設 1」標籤在沒有範圍帶的時刻（4.6 s、8.2 s）仍浮在畫面上。
8. CP2／CP3 合併：先依第 9 節順序處理 K3／K4／K6 與白名單衝突；或先做一個「Demo 彩排用」的合成分支（需使用者同意）。

**Codex**
9. 確認人形場景的物理審查、跨鏡頭、運動面板都是 `NOT_MATERIALIZED_FOR_RUN` 是否為預期；步驟 5（跨鏡頭候選）需要它們，若不做就把步驟 5 從 Demo 拿掉。
10. D21（C5 規則收緊）與 K1 同步（進行中）。
11. 啟動器在合成副本中要設 `OFFICE_ASSETS_REPO`（它用 git common dir 找資產），並且拒絕 tracked 修改；彩排用的分支要先提交乾淨。
