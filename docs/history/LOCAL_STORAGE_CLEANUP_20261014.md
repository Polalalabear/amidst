# 本機儲存清理紀錄 / Local storage cleanup

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

日期：2026-10-14（Asia/Taipei）。使用者明確要求刪除不再使用的工作樹、封存與實體產物，只留下文件紀錄。舊盤點文件的 KEEP／ARCHIVE 是歷史狀態；本次授權與下表實際結果優先。

實際刪除項目刪前配置空間合計：5.384 GiB。這是各項 du 配置空間估計；APFS／系統磁碟的最終可用空間可能不同。

| 原位置 | 刪前 MiB | 結果 | 原因 |
| --- | ---: | --- | --- |
| `/Users/polalabear/Developer/amidst/data/pilot/worktree_archives/20261008-cleanup` | 554.91 | DELETED | 3份退役worktree輸出＋重複recovery；保留manifest/receipt |
| `/Users/polalabear/Developer/amidst/data/pilot/phase1_finalization_human_review_20261006` | 66.16 | DELETED | 媒體均有live相同副本；只留Markdown/JSON紀錄 |
| `/Users/polalabear/Developer/amidst/data/pilot/phase1_finalization_human_review_20261007` | 888.05 | DELETED | 媒體均有live相同副本；只留Markdown/JSON紀錄 |
| `/Users/polalabear/Developer/amidst/blender/working/checkpoints/phase1-semantic-scene-20261005/school_v3.blend` | 446.61 | DELETED | 與canonical v3 SHA256完全相同的備份；asset_manifest保留 |
| `/Users/polalabear/Developer/amidst/.venv` | 712.09 | DELETED | 退役canonical環境；目前服務使用finalization環境；uv.lock保留 |
| `/Users/polalabear/Developer/amidst/.pytest_cache` | 0.17 | DELETED | 可重建工具快取 |
| `/Users/polalabear/Developer/amidst/.ruff_cache` | 0.06 | DELETED | 可重建工具快取 |
| `/Users/polalabear/Developer/amidst/.mypy_cache` | 25.93 | DELETED | 可重建工具快取 |
| `/Users/polalabear/Developer/amidst/src/amidst/__pycache__` | 0.71 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/benchmark/__pycache__` | 0.05 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/visualization/__pycache__` | 0.04 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/experiments/__pycache__` | 0.01 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/datasets/__pycache__` | 0.06 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/graph/__pycache__` | 0.03 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/navigation/__pycache__` | 0.04 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/simulation/__pycache__` | 0.16 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/storage/__pycache__` | 0.01 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/evaluation/__pycache__` | 0.03 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/reconstruction/__pycache__` | 0.02 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/geometry/__pycache__` | 0.06 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/events/__pycache__` | 0.01 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/domain/__pycache__` | 0.14 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/observation/__pycache__` | 0.03 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/src/amidst/debug/__pycache__` | 0.01 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/scripts/__pycache__` | 0.58 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/tests/unit/__pycache__` | 2.21 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/tests/integration/__pycache__` | 0.46 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/tests/boundary/__pycache__` | 0.34 | DELETED | 可重建Python bytecode |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/development/probe1` | 0.01 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/development/probe2` | 84.71 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/development/probe3` | 104.05 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/development/final` | 104.05 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/reproduction` | 166.45 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_abc/research/test/final` | 41.62 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_repair_0511/research/development` | 56.98 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/phase2_repair_0511/research/test/reproduction` | 87.56 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/test/reproduction` | 207.94 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/test/frozen` | 102.67 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/development` | 110.88 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/development_pixel` | 24.54 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/development_selection` | 23.93 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/accuracy_v2/baseline` | 15.64 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/simulation_v1` | 3.37 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/simulation_v2_reproduction` | 3.55 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/local_camera_dev_v1` | 7.09 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/data/engineering/local_run/blender_physical_v1` | 1.84 | DELETED | 過期probe／重複重建／舊版本；curated receipt與現行final/certified保留 |
| `/private/tmp/amidst-cleanup-audit-20261013` | 648.25 | DELETED | 10/13已結束隔離稽核；收據另存canonical，連結不跟隨 |
| `/Users/polalabear/.codex/worktrees/phase1-preview-workspace/amidst` | 905.31 | DELETED | 04c699d已整合；188份非快取資料已有相同副本；退役8768 |
| `/Users/polalabear/.codex/worktrees/54d9/amidst` | 14.63 | DELETED | 9月無有效registration的舊系統；只留文字文件＋SHA inventory |
| `/Users/polalabear/.codex/worktrees/c93d/amidst` | 13.94 | DELETED | 9月無有效registration的舊系統；只留文字文件＋SHA inventory |
| `/Users/polalabear/.codex/worktrees/db5d/amidst` | 85.18 | DELETED | 9月無有效registration的舊系統；只留文字文件＋SHA inventory |

保留 canonical school_v2／school_v3、仍被使用的 wall-marked 模型、目前人工核對資料與復原輸入。未改寫 Git 歷史、分支、main 或 frozen refs，未 push／merge。

phase1-finalization 與 demo-v1-main 仍在使用，保留程式、未提交變更、目前資料、環境、模型權重及 PostgreSQL。6.16 GiB 的 Ollama 模型是現行依賴，不是舊封存。已排除目前 abc/test/certified、repair/test/final、accuracy_v2/test/final 及共同 local_camera_v1/test/checkpoints/final。

三個 9 月 orphan checkout（54d9／c93d／db5d）的文字文件及 path／SHA256 inventory 已留在本文件旁的 storage_cleanup_20261014。其舊程式 bytes 不保留，且目前 Git 無法重建；沒有原始 .blend。db5d 的 .git 曾指向被 demo-v1-main 重用的管理資料，刪除僅針對 orphan 實體，不操作該 Git registration。

10/06、10/07 舊人工核對副本的 Markdown／JSON 紀錄已保存，媒體與副本程式／HTML刪除。舊 approvals_recorded locator 退役；hydration 使用仍保留的 live human_review，其 pinned manifest SHA256 為 923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187。

10/08 archive 原 manifest 和 cleanup receipt 作為文件保留，三份舊工作樹輸出與重複 recovery bytes 刪除。歷史試跑與已刪媒體不能再直接還原；歷史驗證結果不代表本次重跑。

後續清理只保留文件／必要的現行資料；不再把已退役大型產物移入另一個封存目錄。仍在使用的 finalization 工作樹須等共享 Phase 2 與 demo 依賴移轉完成後才可移除。

### 驗證

本輪只做儲存清理、檔案完整性與文件檢查，沒有重跑正式 benchmark 或全套程式測試。原始 Blender 的 SHA256／size／mtime 均未改變；live approved review 的272 artifact＋29 review input hashes及 pinned manifest相符。8016／8017／獨立demo57547均HTTP200，退役8768已停止。現行 hydration 範例已移除失效 locator。詳細機器收據在 canonical docs/history/storage_cleanup_20261014/receipt.json。既有 checkpoint heartbeat已更新為不建立新大型封存，仍等待共享Phase2與runtime依賴結束。

刪前專案 du：13.514 GiB。
刪後專案 du：9.775 GiB。

## English

The user authorized removal of unused physical checkouts, archives and generated artifacts while retaining document records. The table records actual deletion, without creating another bulk backup. Active engineering/demo inputs, environments, model weights, databases and original Blender sources remain. Old orphan source bytes are not recoverable from current Git; their documents and hash inventory are retained. Retired historical outputs cannot be directly restored, and historical validation is not a new test run.

## 2026-10-14 再盤點：剩餘空間與下一批候選（尚未刪除）

本節是唯讀資產盤點，僅新增文件紀錄；沒有執行下一批刪除。最新專案配置空間約 9.905 GiB，外部 main demo checkout 約102.6MiB另計。Phase 2仍在執行完整回歸，不能移除其目前工作樹或測試中產物；測試持續產生快取／dump，大小會浮動。

| 不重疊內容 | 大小 | 判定 |
| --- | ---: | --- |
| Ollama模型 | 6.16GiB | 7B約4.36GiB為目前provider；3B約1.80GiB未被選用 |
| canonical Blender資產 | 1.31GiB | 現行v3約446.6MiB；舊v2與wall-marked合計892.1MiB |
| Python .venv | 774.8MiB | 8016／8017與回歸測試共用，保留 |
| PG cluster／backups | 約272MiB | 保留正式amidst_abc；舊restore DB另列條件式候選 |
| 其餘工程／研究與canonical資料 | 約1.01GiB | RGB、評測、ledger、scene audit及歷史輸出混合，逐項分類 |
| human_review完整包 | 126.2MiB | pinned manifest、目前人審與重現輸入，保留 |
| 其他程式／前端／Git／文件／快取 | 約0.29GiB | Git、程式與工作台依賴保留；可重建快取另列 |

### 已確認目前開發／demo沒有選用的優先候選

以下估計合計約1.95GiB；工具快取需等正在執行的回歸結束後清理。大小為盤點值，包含文件紀錄的候選只刪未用實體／重複檔，保留curated receipts及必要manifest。

| 項目 | 大小 | 處理邊界 |
| --- | ---: | --- |
| Ollama qwen2.5:3b-instruct | 約1.80GiB | 現行兩個provider都pin 7B；3B的unit tests使用mock HTTP，無需實體weights。用模型管理生命週期移除，保留7B共用template/system blobs；3B digest357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b |
| mypy／pytest／Ruff／repo及venv Python bytecode | 約72.3MiB | 可重建；不移除.venv的套件本體 |
| root data/pilot/phase1_finalization_20261006/local_run/{diagnostics_pre_reader,diagnostics_pre_preview,diagnostics_sidecar_draft,dataset_provenance_draft} | 41.89MiB | 舊草稿，保留gallery的6PNG＋6RRD及摘要 |
| root data/pilot/school_v3_multisite_20261005/*/{trajectory_preview.gif,representative/*.png} | 18.52MiB | 未使用衍生預覽；保留300 raw RGB及dataset metadata |
| root data/pilot/phase1_robustness_20261006/{scenarios,visualization_overview} | 10.45MiB | 無現行固定依賴；保留根目錄results/summary/verification |
| root data/pilot/retained_checkpoints/phase1-finalization_20261013/blender_physical_review_reruns 的8PNG＋2MP4 | 1.32MiB | 已逐檔等同live rerun；保留JSON／MD、人審DB／JSONL |
| live data/engineering/local_run/accuracy_v2/test/final/{cards_final,review_cards,evidence}/*.png | 3.70MiB | 21張舊卡片；目前使用cards_review，不能刪cards_review或整個test/final |
| live data/engineering/local_run/{workbench_20261010/*.png,workbench_v1/website_audit_20261008.png,workbench_v1/workbench-desktop.png} | 0.29MiB | 舊截圖；保留JSON與workbench_v1/reviews.sqlite3 |
| live data/engineering/local_run/local_camera_v1/test/cards/*.png | 0.88MiB | 7PNG均已有checkpoint/final/cards相同副本；無8012舊服務 |
| live data/engineering/local_run/local_camera_v1/test頂層12JSON | 9.93MiB | 全部等同checkpoint/final；保留test/rgb、simulation及checkpoint/final。檔名為cards_receipt、registry、package、topology、runtime_config、behavior_config及兩模式events/inference/perception JSON |

### 需先退役舊流程或等共享任務完成的候選

| 項目 | 大小 | 仍需確認／影響 |
| --- | ---: | --- |
| root blender/school_v2.blend | 444.73MiB | 非目前workbench來源；舊CLI defaults與4個optional Blender regression案例仍使用。刪除將失去舊v2重現，不能宣稱原完整驗證範圍不受影響 |
| root blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend | 447.38MiB | 現行runtime不開啟，gallery只需已有預覽；刪除將失去該historical pilot的原場景 |
| root data/pilot/phase1_wall_pilot_20261005/office/frames | 39.48MiB | 100張舊獨有RGB，與multisite並非副本；目前demo不讀取，退役後無法重播原圖像驗證 |
| root data/pilot/school_v3_pilot_20261005/frames | 42.41MiB | 100張舊corridor RGB，目前demo不讀取；保留trajectory-plan provenance及gallery預覽 |
| live data/engineering/local_run/phase2_abc/research/development/certified | 104.05MiB | 只剩historical protected-file hash紀錄；目前05 baseline讀test/certified。等待05共享驗收完成後才退役舊development保管要求 |
| live data/engineering/local_run/local_camera_v1/development | 13.07MiB | 上述舊development baseline的來源；與該baseline一起處理 |
| live frontend/product/node_modules | 22.25MiB | 舊8020依賴，目前無8020 listener；legacy API／回歸仍可能使用。8016的workbench/node_modules必須保留 |
| live data/engineering/local_run/phase2_abc/postgres/backups的9份舊dump | 5.56MiB | 盤點中回歸又新增第10份，不刪整個backups目錄；按舊dump receipt與時間逐項處理 |
| PG中9個無連線的舊amidst_restore*測試DB | 約98.41MiB logical DB size | SQL生命週期清理，不能rm cluster/base；回歸持續產生新DB，刪前重查。此值不當作實際filesystem回收保證 |

### 保留與checkout收斂

root=/Users/polalabear/Developer/amidst；live=root/.local-worktrees/phase1-finalization。

必留現行school_v3.blend、7B模型、Python環境、amidst_abc正式DB、目前Agent／人審ledger、operator各版本、local_camera test/checkpoints/final、test/rgb與simulation、ABC test/certified、repair test/final、accuracy live cards_review、Blender現行camera/motion/association/physical輸出及job ledger。

canonical data/scene_audit有約116.61MiB與live相同內容，但所有69檔皆Git tracked；不列為可直接rm的ignored副本。待checkout整併時收斂，不改寫Git歷史。

finalization整份約7.92GiB主要包含以上依賴，不是7.92GiB可刪封存。main目前沒有獨立.venv或engineering local_run，8016／8017仍由finalization服務；必須完成必要依賴移轉、共享工作驗收與未提交變更發布後，才可移除checkout。移存仍需要的模型／DB／環境只改位置，不等於回收其空間。

盤點期間新增 `root/.local-worktrees/phase1-case23-formal`（約90.6MiB），對應目前執行中的「檢查 Phase 1 進度」工作；暫不列可刪。上述其他程式／文件項包含這個工作樹。PG因並行restore回歸亦增長，總量約9.9GiB是本輪snapshot，不把新增項目誤列成本輪刪除。
