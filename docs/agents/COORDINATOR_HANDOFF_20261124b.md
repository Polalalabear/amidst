# 協調者交接 2026-11-24（下午，第二份）

快照時間 2026-11-24 16:40。接在 [20261124](COORDINATOR_HANDOFF_20261124.md) 之後，只寫變動；**之後的狀態以 #93、#674 和各 PR 為準**。新的協調者全程用繁體中文回覆。

## 0. 版本與環境

- `main` = `6afb4f7614375abf67d3d640fb8abfb6585b0527`（含 #712、#713）。下一個決策號 **D373**。
- 8785 pin 仍是 `c988ed60`，8785 沒有在聽（原因 UNKNOWN）。8791（PID 45196，舊版 LIVE）、8795、8796 在聽，都沒動。
- 磁碟 9.8 GiB。第三個寫入者開工前要 ≥ 9 GiB；程式保護 8 GiB；剩 5 GiB 停。
- OpenAI 帳本上界 USD 80.18，另有 #686 的 USD 0.110643 是否已計入請看帳本；使用者要求用到 90 才叫（D372）。

## 1. 本段新決策

| 號 | 內容 |
| --- | --- |
| D370 | E5 數字現在就填進論文、海報、簡報 |
| D371 | 合併 #712（`384e9327`）、#713（`6afb4f76`） |
| D372 | 同意把 gate 的 Agent 補跑所需合成影格送 OpenAI；費用用到 USD 90 前不用問。不含 #675 的 LIVE 外傳 |

封面的姓名、學號、指導老師、系所由使用者自己填。疑點不改系統，寫進論文討論，期限後再做。

## 2. 工作（依類型）

### 8785 demo 與驗收

| 項目 | 預計產出 | 進度 | 卡在 |
| --- | --- | --- | --- |
| #700 gate 第三次 | edb642c6 的 gate 全 PASS | `local/evidence/gate-pin-20261124-r3/RESULT.txt`（SHA-256 `9f8135c67a84ffa4fb5212bfbfd000dfba5c207e5ec27f14c3738e0995667b01`）只缺三項 Agent 重播的離線收據，其餘全 PASS | Codex-W 補跑 r3b（進行中，`local/evidence/gate-pin-20261124-r3b/`，尚無 RESULT） |
| 換 pin | 8785 換到新版 | 未開始 | gate 全 PASS；再問使用者：先用 edb642c6，或等 #714 合併後重跑 |
| #714（#710）前台 3D 與位置估計 | `/scene3d/`、估計與 UNKNOWN 標示 | head `e008d715`，CI 綠，Sonnet 複審 APPROVE（程式／Node 層） | 正式 launcher 另一 port 實跑、截圖給使用者看過才合併 |
| AC1–AC8 重走、README 中英文 | 驗收紀錄；README 補 E3、E5 結論 | 未開始 | 換 pin |

#714 的已知可見行為：2D 上下方向翻轉；多數播放時間估計顯示 UNKNOWN（最後觀測 A4-1 49.8 s、B4-1 41.8 s）；半徑圓可能被 SVG 裁切；`estimate_reason` 由 null 改 `EST_XY_MISSING` 要在 PR 註記。Opus 裁決留言的 effort 記為 low 是填錯，實際 UNKNOWN。

### 研究紀錄與報告

| 項目 | 預計產出 | 進度 | 卡在 |
| --- | --- | --- | --- |
| #715 論文與 E5 數字總表 | 論文完整草稿 | head `3dcd505e`，CI 綠；Sonnet 審查 NEEDS_CHANGES：數字 2325 列 0 差異，只缺討論文字 | paper session 修改中（§4.6 第 9–12 點、§5、影格來源）；之後 review-715 複審，APPROVE＋CI 綠就合併 |
| 海報、簡報 | LOCAL PPTX／PDF | 完成，另有小修（影格來源寫法、規則 Agent 敘述、表 1 右緣） | poster session 修改中；沒用 PowerPoint／Keynote 開過 |
| 設計問答 | [DESIGN_QA_20261124](../evaluation/DESIGN_QA_20261124.md) | 本 PR | 審查 |
| H9、ReID、查找實驗 | 新的預先登記 | 未決定，期限後 | 使用者 |

研究結論（不變）：單張辨識 Agent 較好（H5 有條件成立）；接進追蹤未得到支持（H1、H8a、H8b、H8d 不成立，H8c 無法判斷）。

### 即時模式／流程

- LIVE 外傳（#675）沒有同意；E3 預登 §7.7 真 LIVE 驗證沒跑。
- #713 後 CI 會跑 `tests/live_mode`，但瀏覽器類與 N6 的測試在 CI 仍會跳過。
- #699、#704、#680、#612、#594 仍 OPEN，標籤待整理。#676／#589 §4.5 UNKNOWN 回退：使用者沒有回答，**不算核准**。

## 3. LOCAL 產物

| 路徑 | SHA-256 | 重建 |
| --- | --- | --- |
| `local/evidence/cx-h6-8cam-20261123/`（29 檔＋manifest，DELIVERY_MANIFEST） | `79ab85849c6c5a405f9ab950a1b477d41cb078e7da9382c60f6d9f90eb443a0e` | 付費收據，不可免費重建 |
| `local/evidence/presentation-pack-20261123/deliverable-e5-20261124/poster/poster_A1_academic_e5.pptx` | `3bffe1c9c1a48244b74ea828f0ff2e5054c1f3e5ce60ae42466280077135ea93`（小修前） | 可由 session 腳本重做 |
| 同上 `slides/amidst_slides_e5.pptx` | `09dc0c9bc292a4e3f75ce8c7949eae6f1158c22ee59073832cf9b9944d86a5e9`（小修前） | 同上 |
| 同上 `slides/amidst_slides_e5.pdf` | `4a6886d5fde3b91783ef9ea8ffaca3be8177f324abedb7d6b597cae1e6622006`（小修前） | 同上 |

小修後的雜湊以該資料夾 README 為準。

## 4. 可續用的 session

| 用途 | id |
| --- | --- |
| 論文 #715 | `local_4671e5fe-f891-4d3f-a1cc-b2c086eb8b09` |
| #715 審查 | `local_5e831abb-6e81-46e6-8297-5f1159c3119c` |
| #714 審查 | `local_746d85c1-25fd-45c0-ab1f-994f340618de` |
| 海報、簡報 | `local_8e66df39-66b1-482c-95d5-e2efb440ed42` |
| GitHub 同步（Haiku） | `local_0db3f8d5-a5dd-417c-a570-fbe36e21625a` |

## 5. 第一件事

1. 看 #715 新 head 與 CI，請 review-715 複審，APPROVE 就 merge commit。
2. 派 #714 實跑與截圖（正式 launcher、另一 port、預設網址、無頭），截圖給使用者看。
3. 等 r3b；全 PASS 就問換 pin 時機。
4. 看海報小修後的預覽。
5. 換 pin 後重走 AC1–AC8、更新 README、請使用者驗收。
