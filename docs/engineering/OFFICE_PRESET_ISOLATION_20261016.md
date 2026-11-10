> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# C3b：場景與品質對應失敗隔離（2026-10-16）

規格依據：整合分支 `cfdc569` 的 [C3b](../agents/OFFICE_DEMO_TASKS.md)，追蹤 [issue #13](https://github.com/Polalalabear/amidst/issues/13)。實際 launcher 驗證 commit：`c750238`；後續不可讀非預設檔案的指紋補強另以測試覆核，程式 SHA-256 見收據。本項接續已合併的 PR #12，不重跑渲染或改動原資產。

| 失敗 | 處理 |
| --- | --- |
| 預設場景無法載入 | 啟動失敗，向上傳遞錯誤 |
| 非預設場景缺檔或一般載入失敗 | 其他場景繼續載入；bootstrap 清單保留 scene_id／中文標籤，附 `status: UNAVAILABLE`、`available: false` 與原因 |
| 品質對應失敗，例如 `QUALITY_COMPONENT_MISMATCH` | 保留原索引、位置、refs 與重建；該場景品質旗標改為 `NOT_EVALUATED`，reasons 附失敗代碼 |
| safe-input／RGB hash、來源綁定、pin／stale 或媒體完整性不符 | 直接拒絕，不降級為不可用或未評估 |

不可用場景只保存清單 metadata，不建立假的 SceneAdapter、來源／run、ReviewStore 綁定或媒體授權。對外原因只輸出穩定錯誤碼，不含私人檔案路徑。presets 清單的 schema、重複 ID 或缺少預設場景仍是設定錯誤。

品質降級會在 scene snapshot 附 `contact_quality_status: {status: NOT_EVALUATED, reason: ...}`。原 v1 觀測仍維持 31 點；控制場景被拒絕的 v2 點仍是 `MISSING`，不藉降級恢復位置。品質層不吞掉 `QUALITY_RGB_HASH_MISMATCH`；v2 producer 回報的 RGB hash 錯誤也在建立索引前拒絕。

launcher 的 preflight 同樣隔離非預設場景缺檔，指紋持續涵蓋每份 fixture 與 bundle manifest／safe inputs；缺檔以明確 `MISSING` 狀態、不可讀的非預設檔案以 `UNREADABLE` 狀態入指紋，新增或移除檔案會改變指紋。readiness 仍核對完整場景清單與預設場景，跳過已宣告不可用的場景影格檢查，輸出 `PRESET_READINESS=DEGRADED` 與 `PRESET_DETAILS`。品質降級也會出現在此輸出。`WORKBENCH_READY=YES` 表示預設工作台可用，不能解讀成所有場景皆可用。

只執行 `tests/workbench/test_office_demo_presets.py` 與 `tests/workbench/test_office_launcher.py`：**24 passed**。包含指定的「控制資料不存在時 Office 仍可啟動」及「品質對應失敗時 Office 仍可啟動且旗標為 NOT_EVALUATED」，另驗預設缺檔／非預設 hash／品質 RGB hash 仍拒絕，以及 degraded readiness／缺檔指紋。正常 Office 七組 canonical 回歸 hashes 保持一致；降級測試驗證原 index snapshot、query 位置與 refs 不變，cross-camera／physical-review 仍可取得未評估旗標。相關 ruff 與 `git diff --check` 通過。

實際 launcher 使用暫存 presets，僅將控制 bundle locator 指向不存在的暫存路徑，沒有移動原素材。Office 啟動、雙鏡頭影格 HTTP readiness 與 31 點 query 通過；控制場景列為 `PRESET_DATA_MISSING`，readiness 顯示 DEGRADED；第二次啟動重用相同 PID／URL。驗證服務已由官方 ownership-checked launcher 停止，其他既有 Demo／PG／Ollama 保留。精簡收據見 [JSON](OFFICE_PRESET_ISOLATION_20261016.json)。品質失敗情境使用測試注入，沒有修改正式 producer 或資產來製造失敗；本次未做瀏覽器視覺驗收。
