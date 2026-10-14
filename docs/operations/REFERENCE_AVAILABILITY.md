# 引用可用性與原路徑 / Reference availability

核對日期：2026-10-14。文件來源與目標檔案由Git tracked-path inventory核對；沒有讀實作程式碼或重新掃描raw assets。
目前入口見[文件索引](../README.md)。公共導航應使用存在的Git文件／固定SHA／已核對tag；
private配置、已退役V5–V8 raw、舊tmp worktrees與runtime locator使用明確離線路徑，不假造公共連結。

## 保持原bytes的review與aliases

`docs/PHASE1_CORRIDOR_SCOPE_REVIEW.md` 是原hash-bound review input，保留其byte內容；
其8次歷史相對引用指向以下5個ignored source-only資料，GitHub clone沒有這些raw檔案：

- `data/finalization/reviewed_branch_discovery_v7/source_supported_proposal.json`
- `data/finalization/reviewed_branch_discovery_v7/source_visibility.json`
- `data/finalization/reviewed_branch_discovery_v7/actual_source_cameras.json`
- `data/finalization/reviewed_branch_discovery_v7/manifest.json`
- `data/finalization/reviewed_branch_discovery_v8/source_visibility.json`

這些連結保留為原證據內容，列為**歷史離線引用**；不將review改写或把新的formal輸出放進舊路徑冒充原輸入。
現行formal acceptance與materialization來源以文件索引的043bed2 scoped release重建指南為準。
原benchmark protocol／geometry provider與必要路徑别名同樣保持；工程樹的三個symlinks可使用本機原入口，
GitHub導航直接指向其分類正文。Symlink URL的相對路徑解析不同，不宣稱它是網頁轉址。

## 歷史與当前讀法

既往PASS／BLOCKED／FROZEN、測試數字、hash、日期與failed receipt保留各自checkpoint。
目前狀態從交接與最新final report讀取；不要把old續作prompt當執行指令。
Tag只保存Git內容；需要raw、Blender、模型或DB時先核對本機依賴與原locator。
固定GitHubSHA的文件連結經物件／Markdownanchor核對；外部服務網址是文件引用，沒有於本輪呼叫runtime服務。

English: Public navigation resolves against Git-tracked paths and pinned document objects.
Private/retired raw paths are offline references. The original hash-bound corridor review retains eight references
to five ignored source-only files; these are documented exceptions, not downloadable GitHub assets.
Locked documents, aliases and original receipts remain intact. This document-only check does not rerun code or restore missing raw data.
