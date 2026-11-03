> 已封存（2026-10-27，D91），見 [封存索引](../../archive/ARCHIVE_20261027.md)。

# Q1–Q5 LOCAL 交接文件公開整理

這是 2026-10-26 整理的歷史文件與 metadata，目錄名稱保留原工作日期 2026-10-25。五份原文件來自 2026-10-23 至 2026-10-25；原 LOCAL 文件與素材均未修改。公開 source receipt 的 hash 指原檔，公開整理後的文件 hash 會不同。

從 [CURRENT.md](CURRENT.md) 選擇交接文件；[LOCAL_ARTIFACTS.json](LOCAL_ARTIFACTS.json) 列出完整來源口徑。其餘文件為 [Demo 要求](DEMO_V1_HANDOFF.md)、[結構化要求](HANDOFF_REQUIREMENTS.json)、[靜態審查前置條件](BASELINE_READINESS.md) 與 [歷史工程組成](DELIVERY_COMPOSITION.json)。

## 歷史與現況

原文字的「目前／最新／仍需」、PR 狀態、model／硬體估算、測試、效能及磁碟數字皆是來源日期的紀錄。現行 G4 核准、圖／參數凍結、正式 RGB／索引／baseline、獨立複核與 merge 狀態為 **UNKNOWN：本文件任務未重查**。本文件不核准 gate、不更改 D65，也不把歷史工程資料轉成正式分母。

這份交付不是 CX-4 的整合產品，不是 P1／P2／G4 驗收，也不是已驗證的 Windows 包。現行新版與一鍵可攜入口由 CX-4／CX-10 另行發布及驗證。歷史範圍提案不覆蓋後續已核定的 D73–D78。

## LOCAL 路徑與範圍

Inventory 的所有 artifact 路徑都相對於使用者自行設定的 `AMIDST_ARTIFACTS`；此處不寫個人絕對路徑。它是原始保留包的位置，不代表程式已能換根執行。原包中的硬編路徑、file pins、環境與 localhost 服務要求，需由獨立 relocation 工作驗證，不能用這份公開文字宣稱可攜。

七個 package inventory 只涵蓋各 pinned manifest 列出的 payload，排除 manifest 本身與各自記載的 mutable／editable／cache 範圍。root Qwen 401 檔不包含之後的文件補充包或 CURRENT。各包與五份來源文件有重疊，總數與 bytes 不可直接相加當 unique files、配置磁碟用量或已釋放空間。

原 RGB、private producer、完整錄製與 human returns 都保留 LOCAL，不複製到 GitHub。推論入口仍不得讀 GT、人工答案、renderer 軌跡或 actor ID。歷史靜態圖 metadata 不代表身份已確認或物理可通行。

## 本次實際核對

- 重新 hash 五份命名原文件與七份 package manifests。
- 對歷史組成 533 筆 `commit:path` 查 git blob type／size，全部存在，raw bytes 合計 6,102,204；並與原 delivery manifest 的 path／SHA／bytes metadata 對照。
- r004 manifest 缺 size，只對其列出的 80 檔 `stat`，合計 10,704,193 bytes；沒有讀取圖片或 RETURN 內容。
- 其餘 payload count／size／SHA 取自原 manifest；除上述五份命名來源文件外，沒有重新 hash payload、遞迴掃描包內容、讀 raw RGB／GT／人工答案、渲染或執行模型。

因此可以核對來源與記錄組成，不能宣稱所有現存 payload 已重新驗證完整性。新的 inventory 保留 `hash_source`／`size_source`，區分讀檔 hash、git metadata、stat 與歷史 manifest。

## 核對命令與重現條件

在這個公開文件目錄核對公開副本：

```sh
shasum -a 256 DEMO_V1_HANDOFF.md HANDOFF_REQUIREMENTS.json CURRENT.md BASELINE_READINESS.md DELIVERY_COMPOSITION.json LOCAL_ARTIFACTS.json README.md
```

在 LOCAL 保留根目錄核對一份歷史 manifest，將輸出與 inventory 中同路徑的 SHA 比較：

```sh
cd "$AMIDST_ARTIFACTS"
shasum -a 256 q1q5-qwen3-contention-20261023/MANIFEST.json
shasum -a 256 r004-prereview-team-v2_20261024/MANIFEST.json
shasum -a 256 q1q5-dynamic-baseline-v1_20261025/DELIVERY_MANIFEST.json
```

要核對某個歷史 source blob 大小，在已有對應 commits 的 repository，使用 composition 內的實際 commit 與相對 path：

```sh
git cat-file -s '<commit>:<repository-relative-path>'
```

這些命令核對文件／metadata，沒有啟動產品或模型。完整重現仍需要保留的 LOCAL payload、相同 source composition／環境與模型 pins、適用 source/run/camera/clock/index/graph/parameter bindings，以及相應獨立複核和使用者 gate。錄製中的時間／資源／模型輸出不保證重新執行後逐 byte 相同；遺失素材不能由 metadata 還原，人工回覆不可重造。

本次沒有重跑原歷史命令、focused product tests、完整測試、瀏覽器／Windows／新環境實測，也沒有取得新的正式成效或核准。只做此七份文件的 JSON、相對連結、來源收據、inventory 和 whitespace QA。
