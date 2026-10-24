# r004 正式產製準備

Refs #196、#118、#195。配置 `configs/q1q5/r004_production_v1.json` 固定既有 D70 設計、八台相機校正 hash、來源 hash、CPU/FP32/seed7/threads2；A4 四台、B4 五台，各30秒/5fps/960×540。正式 run、相機子集、clock、RGB、參數與核定收據保持 null，不能拿示例代填。

`scripts/build_q1q5_pinned_index.py --plan <canonical.json> --plan-sha256 <sha256> --output <new-report.json>` 只寫 BLOCKED 缺件清單並退出2，不載模型、不讀影像。來源來自原審查包鎖定安全 metadata，沒有重新 hash 原 .blend/weights，也不讀 RETURN、GT 或事件腳本。原審查包不改。

後續真正執行另需 `--binding <canonical.json> --binding-sha256 <pin> --permit-real-rgb --output <new-local-dir>`。binding schema `q-demo.index-production-binding.v1` 明列 label、scene_revision、registration、camera_ids、source_range_us、clock_mapping、parameter_set、detector_config、approval_receipts。registration 沿 RunRegistration 五個欄位；三份 metadata ref 均為 `{path,file_sha256}`。detector_config 明列 source_root、weights、所有 source_hashes、seed、threads，沿既有 official adapter 核對權重與來源，不下載或換裝置。

五份核定 metadata 分別記 GRAPH_ROI、HSV、PARAMETERS、PROGRAM_REVIEW、RUN_FREEZE；每份含 gate、reviewer、decision=APPROVED、scope_sha256。scope 是整份 binding 排除 approval_receipts 後的既有 canonical content_hash；不接受只有 approved boolean，換 run/camera/time/clock/設定使舊核定失效。此檢查只驗 bytes 與 scope，不能認證 reviewer 身分；人類／獨立審查核定仍須核實 GitHub 收據，測試的 SYNTHETIC 收據不具有權限。

新入口使用明列 registration，沿 load_rgb_playback 和 build_detection_index；scene revision 由固定 r004 計畫提供，不再依賴舊 r003/A-B1 註冊。原 `build_q1q5_detection_index.py` 留存不改。讀取安全包後核對鏡頭、時間、畫格尺寸及校正；不一致在模型載入前失敗。輸出只允許新的 canonical `~/amidst-artifacts/` 目錄、0700，索引 manifest 沿原 writer 最後發布；失敗不寫 COMPLETE 收據。前後 df-k，低8GiB停。重跑需要新目錄。

收據分列安全 metadata 載入、模型載入、完整建索引 wall/CPU/caller lifetime peak RSS。建索引包含 RGB hash/decode、forward、HSV 和 encoding；細項尚未量測時不冒充純 inference fps，inference_fps=null 並寫原因。正式 RGB 產製仍由 #115 的既有授權流程執行；本入口不渲染。

本次 focused 僅驗 pinned registration、scope/核定/參數/clock/校正/磁碟/拒覆寫及合成 PNG+假 detector 的完整 producer。實機 RT-DETR、正式 RGB/index、Claude 獨立核定未由此驗收。B/Draft，不 merge。
