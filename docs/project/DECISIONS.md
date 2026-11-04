# 重要決策摘要（D113～D126）

返回 [README](README.md)。完整決策紀錄在 [#93](https://github.com/Polalalabear/amidst/issues/93)，每條都附原留言連結；本表只做摘要，有出入時以原留言為準。

| 編號 | 日期 | 決定 | 對兩個核心的影響 | 原留言 |
| --- | --- | --- | --- | --- |
| **D113** | 2026-11-02 | demo 的 Q2 切鏡分成兩段：B-05a live（圖未核准，停在 A＋GAP，fail-closed）與 B-05b 預錄（RULE_ONLY 錄製 `2777741d…`，5.15 s 切到 B）。不能說 live 已切鏡，也不能把工程核定說成 G4 | case2 的切鏡要分清楚「系統真的決定」和「圖未核准而不切」 | [D113](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6575688787) |
| **D116** | 2026-11-02 | demo 後大清掃：`main` 成為唯一主幹；解除對其他分支與本機 checkout 的依賴；PR／議題／分支只留重要的，其餘整理後刪除；證據改寫成敘事型紀錄。另補研究企劃（環境清單、跨平台依賴檢查、GitHub Actions 矩陣） | 大整理後半已被 D126 擱置 | [D116](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6579537960) |
| **D116-補** | 2026-11-03 | 刪分支、關 PR 之前，先用腳本證明「只 clone main 就能跑」（`verify_clean_clone`）；整理前後結果一致才刪 | 驗證腳本是 D126 保留的工作 | [D116-補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594014349) |
| **D117** | 2026-11-02 | 不接資料庫，維持檔案式資料（JSONL 索引、凍結錄製、PNG、state-root）；必要文件（PRD、系統架構、介面、規則、README、決策紀錄）在清掃時一次更新 | 兩個核心都用檔案式索引；本文件包是對外說明，不取代 D117 的必要文件更新 | [D117](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6579723510) |
| **D118** | 2026-11-02 | CX-7 渲染的磁碟暫停門檻降到 8 GiB；8～10 GiB 時不開新的寫檔 session；低於 8 GiB 所有寫檔都停 | D124 重渲染與 D126 擴充場景都沿用 8 GiB 門檻 | [D118](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6580320736) |
| **D120** | 2026-11-03 | 複雜事件 A4-1／B4-1 以唯讀多鏡頭播放進 demo，獨立成包（`frontend/event-viewer/`，#399），不解凍 FEAT-9；只有 ENGINEERING 影像，無推論 | 複雜事件目前只能「查看」，還沒有查找與追蹤 | [D120](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594169791) |
| **D124** | 2026-11-04 | 首要目標是複雜事件的真實追蹤：追蹤決策只能來自系統推論（#118 → CX-8 RULE_ONLY）。授權 Codex 重渲染 A4-1／B4-1（人物轉身、看得出正反面，其他不變，產生新 run）；先重渲染再追蹤，只跑一次；參數集要使用者核定；所有畫格顯示虛擬世界時間（Asia/Taipei，DECLARED_DEMO_CLOCK） | case2 在複雜事件上的資料來源；宣告時鐘的顯示規則 | [D124](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061) |
| **D125** | 2026-11-04 | 大整理 8 項照盤點建議執行（要刪的先寫進敘事紀錄；有證據價值的分支不刪；合 main 與刪分支仍要重驗與授權）。#405、#407 已合併，`mainline/q1q5`＝`796cc17`。驗收條件：輸入以選取為主；三種人物事件都有查看、追蹤（單／多畫面）、查找；1×／1.5×／2× 倍速 | 選單優先、倍速是兩個核心的共同要求 | [D125](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251) |
| **D125 補** | 2026-11-04 | P2 納入 Q4 正式 T／F 評估（#342）；組員 Q4 標註包可先做 | 已被 D126 擱置 | [D125 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621022288) |
| **D126** | 2026-11-04 | 系統核心縮為「追蹤」與「查找」，強調輔助、不求精確。只留 T2 重渲染和驗證腳本；M1–M4、Q4 正式標註包、Colab 包、大整理後半都擱置；報告初稿改以兩個核心為主。擴充 Office 場景（多間教室＋COCO 物件，Codex 做）。Claude 寫 PROPOSED 契約和驗收測試，Codex 照測試做前後端。倍速跟不上時自動降速並顯示實際倍速 | 本文件包的依據 | [D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) |

## 相關但不在必列範圍的決策

| 編號 | 摘要 | 原留言 |
| --- | --- | --- |
| D121 | 研究企劃 #397 的決定 A～G；§D.7 錄影 fps 改成兩張表 | [D121](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594412627)、[D121 補充](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594452943) |
| D64 | Q1–Q5 主線例外：Agent 可在合法 top-k 候選內決定是否切鏡；候選與排序仍由決定性模組產生 | `docs/DEVELOPMENT_RULES.md`@`796cc17` 第 63 行 |

2026-11-04 讀取 #93 時，D126 之後還沒有新的 D 編號留言；之後的決策以 #93 最新留言為準。
