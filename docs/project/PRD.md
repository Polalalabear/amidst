# PRD：Amidst 查找與追蹤

返回 [README](README.md)。規格細節見 [SPEC.md](SPEC.md)，術語見 [GLOSSARY.md](GLOSSARY.md)。

## 1. 問題

一個場地裝了很多台監視鏡頭時，要知道「某個人或某樣東西在某段時間出現在哪裡」，通常只能一台一台看錄影。鏡頭之間還有拍不到的盲區，目標走進盲區後，要靠人判斷它可能從哪台鏡頭再出現。

Amidst 要解決的是這兩件事：

1. **查找**：給時間範圍和地點或特徵，直接列出拍到目標的鏡頭畫面。
2. **追蹤**：選定目標後，畫面自動跟著切到看得到它的鏡頭；看不到時，告訴使用者它大概會往哪裡去。

## 2. 目標使用者

操作工作台、需要在多台鏡頭裡快速找到目標的使用者（[D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045)）。具體角色（例如監控室值班人員）與使用場域：**待補**，repo 文件與 #93 沒有定義使用者角色。

## 3. 產品定位：輔助、不求精確、快速找到可能位置

使用者原話（D126）：「這兩個是系統核心，其他都能擺著或廢棄，只有這兩個一定要先做出來。」並且本系統強調「輔助」，**不追求精確**，只要讓使用者**快速知道目標大概在哪**。

這個定位帶來三條設計原則：

- **寧可說不知道，也不假裝找到**：沒偵測到不等於不在畫面；推論和觀測分開標示（`OBSERVED`、`INFERRED`、`MISSING`、`UNKNOWN`，見 [SPEC §3](SPEC.md#3-證據狀態)）。
- **每個答案都能追溯**：畫面、偵測、決策都帶 source／run／clock／hash（[`AGENTS.md`@`796cc17`](https://github.com/Polalalabear/amidst/blob/796cc176cd40bedbfe701b95192d3c8679755aa9/AGENTS.md) Shared rules）。
- **先用選單**：輸入以選取為主，降低輸入錯誤（D126；[D125-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251)）。

## 4. 使用情境

### 4.1 case1 查找

> 「下午兩點到兩點十分之間，R101 有沒有人？」或「這段時間哪台鏡頭拍到椅子？」

| 步驟 | 使用者 | 系統 |
| --- | --- | --- |
| 1 | 從選單選時間範圍（必填，台灣時間） | 依宣告時鐘換成來源時間 |
| 2 | 選地點（可空）和／或特徵（可空），兩者至少選一個 | 地點：用 camera_graph 的 `covered_regions` 找涵蓋該區域的鏡頭；特徵：查 RT-DETR COCO 偵測索引 |
| 3 | 看結果 | 列出時間範圍內拍到目標的鏡頭畫面；沒有命中時說「沒有命中」，不代表目標不存在 |

規則來源：[D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) case1。現有 demo 的 B-03 Q1 命中牆是這個情境的早期版本（#397 §E.2.2，head `e6c6ad0`）。

### 4.2 case2 追蹤

> 「穿紅衣服的人現在在哪？跟著他。」

| 步驟 | 使用者 | 系統 |
| --- | --- | --- |
| 1 | 選特徵（必填），地點可空，時間空著代表現在 | 找出符合條件的起點觀測 |
| 2 | 選「單畫面」 | 一直播看得到目標的鏡頭；目標離開就換到另一個看得到的鏡頭，直到完全跟丟 |
| 2' | 或選「多畫面」 | 顯示所有找到目標的鏡頭，目前追蹤所在的鏡頭加框 |
| 3 | 目標走進盲區 | 沒有鏡頭看到目標時，顯示俯視圖和物理預測曲線，標成 `INFERRED` |

規則來源：[D126](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) case2。單畫面／多畫面切換已在 [#408](https://github.com/Polalalabear/amidst/pull/408) 做出 B-05a／B-05b 的版本（OPEN，未合併）；A4-1／B4-1 的追蹤輸出尚未產生（[D124](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)）。

## 5. 非目標

**永久非目標**（[`AGENTS.md`@`796cc17`](https://github.com/Polalalabear/amidst/blob/796cc176cd40bedbfe701b95192d3c8679755aa9/AGENTS.md)：「This is an engineering demo, not identity, physical-safety, or formal research acceptance.」）

| 非目標 | 系統怎麼表現 | 出處 |
| --- | --- | --- |
| 身分確認 | 跨鏡頭只是「條件相符的候選」，`identity_verdict` 一律 `UNCONFIRMED` | `docs/specs/Q1Q5_PRODUCT_SPEC.md`@`796cc17` §1.2 |
| 物理安全、可通行、碰撞 | 區域圖的通道都是 `TOPOLOGICAL_ONLY`、`state=UNKNOWN`；物理通行一律 `UNKNOWN` | `configs/q1q5/graphs/r004/region_graph_v3_1.json`@`796cc17`；`docs/DEVELOPMENT_RULES.md`@`796cc17` 第 56 行 |
| 正式研究驗收 | 這是 Blender 合成場景上的工程 demo，不是 benchmark | #397 §P.1（head `e6c6ad0`） |
| 真實監控影片、即時大規模部署 | 目前只有離線與預錄的合成畫面 | #397 §P.2 |

**目前擱置**（D126-1，不是永久放棄）：

- M1–M4 模型實驗（#397 第二部分）
- Q4 正式標註包
- Colab 外包測試包
- 大整理的後半：合進 `main`、刪分支（D116、D125）

擱置的詳細清單見 [ROADMAP.md](ROADMAP.md#擱置清單)。

## 6. 成功標準

以下是 D126 與 D125-3 定下的驗收條件，量化門檻（例如回應時間、命中率）目前**沒有**定義，寫作 **待補**。

| # | 標準 | 怎麼驗 | 出處 |
| --- | --- | --- | --- |
| S1 | case1：時間範圍必填、地點與特徵至少一個；違反時前端擋下並說明 | 核心契約的驗收測試（契約內容 UNKNOWN，見 [SPEC §8](SPEC.md#8-介面契約)） | D126 |
| S2 | case1：地點查找只回 `covered_regions` 涵蓋該區域的鏡頭；物件查找只回偵測索引有命中的鏡頭 | 同上 | D126 |
| S3 | case2：單畫面在目標離開後換到另一個看得到的鏡頭，直到完全跟丟；多畫面列出所有找到目標的鏡頭 | 同上；#408 已有 B-05b 實測（5.10 s＝A、5.15 s＝B） | D126；[#408](https://github.com/Polalalabear/amidst/pull/408) |
| S4 | case2：盲區時顯示俯視圖與物理預測曲線，標 `INFERRED` | 同上；物理預測路由目前 503，此項待接線 | D126 |
| S5 | 輸入以選取為主 | 瀏覽器驗收 | [D125-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251) |
| S6 | 1×／1.5×／2× 倍速；跟不上時自動降速並顯示實際倍速 | #408 `speed.test.mjs` 與截圖 31 | D125-3、D126-4 |
| S7 | 追蹤決策只來自系統推論，不得用劇本、GT、渲染軌跡、可見性或深度 | 有對應的隔離測試；架構守門 0 findings | [D124-1](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)；[#279 協調](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6620849868) T2 |
| S8 | 回應時間、命中率、跟丟率等量化門檻 | **待補** | — |

## 7. 展示範例：擴充後的 Office 場景

D126-2 決定擴充 Office 場景作為查找的展示範例：

- 多間標註教室（例如 R101～R104），每間有室內鏡頭；
- 放 COCO 可辨識的物件，讓物件查找有東西可找；
- 由 Codex 做；渲染前先查磁碟，低於 8 GiB 就停（D118）。

目前狀態：**尚未產出**。教室數量、鏡頭數、物件清單、渲染長度與 fps 都是 **待補**。

現有可用的基石是 r004 場景（`scene_id=controlled_scene_v1_s001`），7 個區域裡已有 R101、R102 兩個房間，室內鏡頭只有 CAM_R101_IN（`configs/q1q5/graphs/r004/camera_graph_v3_1.json`@`796cc17`）。r004 是否就是「Office 場景」：**UNKNOWN**，#397 §E.3.1 已記錄 r004 檔案裡找不到這個稱呼。擴充版要用哪一個場景為底，等 Codex 的產出確認。
