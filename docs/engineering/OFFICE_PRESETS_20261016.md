# Office 多場景預設與接地品質旗標（2026-10-16）

依 [Demo 計畫 §8](../agents/OFFICE_DEMO_PLAN_20261101.md#8-codex-任務) 的 `78855c1` 修訂交付任務 3。v2 前提 commit `bb3d282` 已推送；整合分支透過 merge commits 納入，沒有 squash／rebase。

| 場景 | 來源與感知 | 可用層 |
| --- | --- | --- |
| `blender-office`（預設） | 原 `blender-pilot-office-baseline-v1`；v1 31 個觀測、位置與 track_ref 保留 | 原影像、查詢、motion／association／physical、Office supplemental display |
| `blender-contact-control` | `blender-contact-control-auditorium-v1`；v2 100 個元件，其中 62 個保留位置、38 個 `MISSING` | 原影像、查詢、來源模型、時間畫面牆；未物化的重建及物理層不可用 |

`configs/office_demo_presets_v1.json` 宣告獨立 fixture、bundle locator、中文標籤與逐場景 `perception_version`。bundle locator 分別相對於 evidence／assets checkout；原素材不複製。每個 bundle 先驗 safe-input hash，再驗自己的 dataset／source／run pin、校正與影格 hash。原 Office fixture 沒有修改。別名只由 `with_display_identity` 改展示身分，不改 source binding。

`contact_quality` 是回應附加欄位；不進入原 Office 索引、source_features、排名、位置或物理判定。query observations、frame query、cross-camera path samples、選定目標回應及 physical review 的 `synchronized_evidence.samples` 都附相應旗標。原 `review_sha256`、candidate／event／observation refs 與 frozen 結果維持。

v1→v2 對應先重算同鏡頭同影格的原 `>30`、4-連通元件；元件全部像素歸屬唯一的 8-連通 v2 元件時，附該元件品質。無法恢復原元件時，才以 v2 包圍框涵蓋 v1 接地點 fallback；多框命中為 `NOT_EVALUATED`／`AMBIGUOUS_MAPPING`，無命中為 `NOT_EVALUATED`。多個 v1 元件對到同一 v2 元件時，全數加上 `AMBIGUOUS_MERGE`。pixel sensitivity 使用 v2 的 ±1 px 地板投影敏感度；未評估時為 null，並非總誤差界或信心值。

本次 Office 31 點皆為 `FLAGGED`，仍顯示原位置。0.4、0.6、1.8、2.0 秒有 `LOW_INCIDENCE`；4.4 秒兩點都有 `LOW_INCIDENCE`、`CONTACT_OCCLUDED`、`AMBIGUOUS_MERGE`。控制場景僅保留點附 `PASS`；被拒絕點不附品質欄位，位置為 null，原因保留於 `missing_reason`。

控制場景以 snapshot 的 `capabilities` 與 `layer_availability` 明示 motion、association、physical_source、physical 不可用。相關讀取 API 回傳 HTTP 200／`UNAVAILABLE` 與該場景 scope；影像、觀測及畫面牆仍可使用。媒體 provider 先按 scene_id 路由，無該場景資料就不授權媒體。兩個 run 的 clock_id 字串原本相同，但驗證使用完整 run／dataset／clock／source_features 綁定，不將 clock_id 單獨當成共同時間來源。

啟動沿用 `./start-office-demo.command --no-open`。Python 與 shell 入口由 Git common directory 找共享資產 checkout；可用 `OFFICE_ASSETS_REPO`、`OFFICE_EVIDENCE_REPO`、`OFFICE_PRESETS`、`OFFICE_BUNDLE` 明確指定既有素材。readiness 核對完整 presets catalog、預設場景順序、逐場景來源與雙鏡頭影格；啟動指紋涵蓋預設清單、每份 fixture、所有 bundle manifests／safe inputs、感知程式與設定，以及既有 frontend／display／vendor 依賴。

驗證見 [精簡 HTTP 收據](OFFICE_PRESETS_20261016.json) 與 `tests/fixtures/office_demo_v1_response_hashes.json`。回歸基準在修改前擷取；合併後的 display snapshot 額外以 `git show 78855c1:scripts/office_demo_backend.py` 的原版程式獨立重算。移除 `contact_quality` 後，snapshot、query、motion、cross-camera、target、physical、physical review 七組回應的 canonical hashes 均相同。target 基準採既有 HTTP schema 的浮點時間格式。

只執行六個相關測試檔：`test_office_demo_presets.py`、`test_office_launcher.py`、`test_office_display.py`、`test_blender_scene.py`、`test_target_reconstruction.py`、`test_perception_v2.py`，全部通過；三個 socket 測試原先受 sandbox 阻擋，取得 localhost 權限後單獨重跑通過。相關 Python 檔案 ruff、shell 語法、`git diff --check` 通過。實際 launcher readiness、第二次啟動重用、缺層 HTTP 200、跨場景媒體拒絕與 59 個 physical-review samples 的品質欄位通過。來源 `.blend` SHA-256／size／mtime 不變，沒有渲染或讀 GT 作推論。驗證服務以所屬 launcher 正常停止，其他 Demo／PostgreSQL／Ollama 保留。

本次驗收限於後端與 HTTP；品質旗標的前端視覺呈現、完整 Demo 操作與真實定位精度仍未驗收。
