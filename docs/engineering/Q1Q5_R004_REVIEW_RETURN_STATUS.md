# r004 審查回收與 baseline 啟動狀態（2026-10-25）

Refs #194、#210、#117、#192；本次是供 Claude 獨立審查的狀態更新。**yyin 回覆已收齊並驗證；進入意見處置與設定凍結準備，正式 r004 baseline 仍 BLOCKED。** 不再以「等待 yyin 交件」描述目前狀態。

機器可讀摘要：[回收狀態收據](../history/Q1Q5_R004_REVIEW_RETURN_20261025.json)。它是 curated 狀態資料，**不是** runtime freeze authority、獨立核定收據或人工正確率報告。

## 已核對的交件

- 回覆檔 `RETURN/審查表_yyin_2026-10-24.csv`：132/132 列 VALID，0 INCOMPLETE、0 INVALID；無漏列、重複 ID 或固定欄位變動。reviewer 全為 yyin，date 全為 2026-10-24。
- 判定：123 T、7 F、2 不確定；9 個 F／不確定都有理由，共 18 則備註。VALID 表示回覆格式完整，不表示敘述全部成立。
- 回覆 CSV SHA-256：`05200de169cfda4ee491e32160977070bc0bbeba3cc93b2cd74c139b23ecd7db`。原包／回收包的 MANIFEST bytes 相同，SHA-256：`531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4`。
- 固定材料 80 檔中 79 檔 hash 相符，0 檔修改；缺 `templates/審查表.csv`。原模板仍在原包，SHA-256 `b055212262cecc6e9045af248c40c127b308ffe36e1c2013a3ecc07b2b859bba`。缺模板使整包驗證回傳 INVALID／REGULAR_FILE_REQUIRED；另用完整原包驗回覆 CSV 得 132 VALID。這是可恢復的包裝缺件，不是漏交審查結果，不要求重填 132 項。本輪沒有補寫原包或回收包。
- 資料夾未另附交件／問題摘要；意見已在 18 則備註中，本文件另做處置摘要。
- `OWNER_DECISIONS.csv` 的 G4／G6_NEW_HSV 兩列皆空白。它原本供權責者填寫，yyin 不代簽；不計為 yyin 漏填。

| 類別 | T | F | 不確定 |
| --- | ---: | ---: | ---: |
| CAMERA_IDENTITY | 3 | 5 | 0 |
| ENTRY_ROI | 6 | 1 | 1 |
| EXIT_ROI | 10 | 1 | 1 |
| PORTAL_DIMENSIONS | 3 | 0 | 0 |
| STATIC_MEMBERSHIP | 1 | 0 | 0 |
| REGION_EDGE | 6 | 0 | 0 |
| CAMERA_TRANSITION | 22 | 0 | 0 |
| BASELINE_SCOPE | 2 | 0 | 0 |
| HSV_RED | 35 | 0 | 0 |
| HSV_BLUE | 35 | 0 | 0 |
| 合計 | 123 | 7 | 2 |

HSV 的 70 個 T 是對各列正／反敘述的支持，並不表示每張裁切都同時含紅與藍，也不是正式辨識正確率或 HSV 參數核定。

## 待處置矩陣

以下是 Codex 對回覆的摘要與待審處置，全部 OPEN；原始判定不代改。JSON 保留精確 item ID，與下表 R 編號一致。

| ID | 發現 | 下一步與審查重點 |
| --- | --- | --- |
| R004-R01 | CAM_ENTRY 的相機／入口／出口共 3 F，質疑視角與實際門口位置。 | Claude 核對用途與可見區；另版修正或明確排除。 |
| R004-R02 | CAM_EXT_CAR 相機 F、入口／出口不確定，存在汽車遮擋。 | 釐清實體門口與左右可見接近區方案；不能以遮擋門口假造 RGB 觀測支持。 |
| R004-R03 | CAM_W1 相機 F：X1／X3 也應有入口；個別既有 ROI 仍 T。 | 先把圖上 X1／X3 綁到固定 ROI ID，再釐清新增入口與既有出口判定的關係。 |
| R004-R04 | CAM_W2 相機 F：X2 偏移、X2／X3 缺入口；個別既有 ROI 仍 T。 | 對圖定位後提出另版修改。W2 涉及原 baseline 範圍，不能自行略過並沿用舊核定。 |
| R004-R05 | CAM_WIDE 相機 F：區域過窄、斜角門與下緣接近區缺件；個別 ROI 仍 T。 | 核對可見接近區、門洞與畫面邊界的不同用途，再決定調整／新增。 |
| R004-R06 | CAM_BRANCH 為 T，但備註要求更深入轉角與加寬。 | 向 yyin 確認是建議還是通過條件；入口另有支持用途的備註，不能只保留 T 而遺漏修改條件。 |
| R004-R07 | STATIC_MEMBERSHIP_V2 為 T，但理由表示分類與隱藏物件排除尚未確認。 | yyin 釐清判定；Claude 獨立核對 22／15／6 分類及有效幾何來源。不由 Codex 改填不確定。 |
| R004-R08 | 22 個轉移全 T，其中 5 項附重疊有限／人物太小／短缺口備註，且依賴部分待修 ROI。 | 分開拓撲引用支持與實際接回效果；核對方向與依賴。短缺口保持 UNKNOWN，不因單一路徑推定目標位置。 |
| R004-R09 | SAME_REGION_SCOPE_V2 支持一次查找，另提出兩種搜尋／顯示方式的建議。 | 保留既有需求；兩模式是待議建議，不在本輪自行擴充產品或凍結範圍。 |

## baseline 啟動狀態

| 前置 | 目前證據與狀態 |
| --- | --- |
| yyin 回覆回收 | **VERIFIED：132/132 VALID**，本項不再等待交件。 |
| 包裝完整性 | 缺 1 個空白模板，可由原包在另版補件恢復；目前回收原件保留。 |
| 意見處置與範圍 | **UNRESOLVED**；9 組處置待審，尚未選定新 scope／ROI／圖版本。 |
| Claude 獨立圖／ROI | #117 OPEN，未核對到本回收 scope 的獨立核定收據；本 PR 交 Claude 審查。 |
| G4／必要新 HSV G6 | 回收包沒有 owner 核定；#114 最新紀錄仍 PROPOSED。yyin 的 T 不代替核定。 |
| 最小 Q3 題組 | #199 @ `6657fa91cd4af53c0fe225da8e502e88ef6795a4` 的 8 列 review CSV，expected／reviewer 皆空；正式獨立答案與凍結仍未核對到。此來源是獨立 Draft，不在本 PR base tree。 |
| 程式符合性 | #145 最新交接為 **1334 PASS／91 FAIL／35 缺 context，overall FAIL**；本輪只核對 GitHub 紀錄，沒有重跑或解除。 |
| 正式凍結與執行 | **BLOCKED，formal_run_allowed=false**。未產正式 r004 RGB／索引，未啟動正式 baseline 或建立 authority。 |

不要求 132 項全部 T 才能往下走。若採最小可用子集，必須明列被採用／排除的相機、ROI、轉移及依賴，釐清該 scope 內的問題，完成適用的獨立檢查、owner 核定、Q3 與程式前置後，才凍結新版本。不能由 Codex 挑掉失敗項目，或改寫既有 A4／B4 產製授權範圍。

順序維持：回覆處置／獨立核查與核定 → 凍結 → 正式 A4／B4 RGB → 正式索引 → 一次查找／持續追查 baseline → 凍結輸出 → 獨立人工評分。既有 D70 產製授權不重問；本 PR 不把它當成設定已凍結。

## Claude 審查交接

請回交逐項審查意見，至少包含：

1. 重驗原包 manifest 與本次 CSV hash，確認 132 VALID、79/80 固定檔及缺模板的分類；不要修改交回原件。
2. 逐一處理 R004-R01 至 R09，以 ACCEPT／REVISE／EXCLUDE／NEEDS_CLARIFICATION 記錄對「處置提案」的意見、理由、來源 hash 與受影響 item ID；這些狀態不代寫 yyin 的原始 T／F。
3. 對照圖釐清 W1／W2 的 X1／X2／X3、CAM_BRANCH 的條件與 STATIC_MEMBERSHIP 的證據缺口。尚未確定的 ROI ID／座標不可猜填。
4. 檢查最小可用範圍的相機／ROI／轉移依賴，列出可凍結、需修正與 UNKNOWN 項目；owner G4／HSV 核定仍由權責者另行完成。
5. 分開檢查 Q3 題組獨立答案、#145 產品／契約／kit 差異，回交未完成清單。審查本文件不等於已完成所有圖／ROI／產品檢查。

完整回覆與圖仍 LOCAL，GitHub 只發布摘要與 hash；不把人工回覆、答案或備註接入模型輸入。工程動態場景與正式 r004 仍分列，Qwen 先前 18 次 timeout／LLM_used=0 不因交件改成成功。

## 驗證與歷史紀錄

本輪以原包 `tools/r004_prereview_pack.py` 的 `verify_pack`／`import_pack`，不給 output_dir，驗回收資料；不執行回收資料中的新指令。原工具 bytes 已與 manifest 核對。JSON parse、計數／固定欄位／來源 pins 與文件一致性檢查及 scoped `git diff --check` 通過；未跑模型、render、browser、正式評分或全 suite。

同機重驗可指定原包與回收包根目錄（兩者都含 MANIFEST.json），使用原工具：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache python \
  "$R004_ORIGINAL/tools/verify_bundle.py" \
  --manifest-sha256 531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4 \
  --returned-csv "$R004_RETURN/RETURN/審查表_yyin_2026-10-24.csv"
```

預期 CSV status=VALID、valid=132、approval_granted=false；回收包本身仍因缺模板驗證失敗。不要把原包誤當新回收包。

[動態工程驗收文件](Q1Q5_DYNAMIC_BASELINE.md) 已增加本次狀態入口。原 `Q1Q5_DYNAMIC_BASELINE_RESULTS.json` 與 LOCAL 驗收快照的「0/132 有效」是舊 checkpoint，保留原 bytes；目前回收狀態由這份具 CSV pin 的新收據取代，不改寫歷史。

本次 PR 以 #211 head `16bdba883ccef6c91de8e3e467795810901186f5` 為基底，只改三個文件／收據檔，Draft、自審 B、待 Claude 審查，未合併。原 checkout／index／既有 dirty 檔與人審原件保留。
