# #416 Argon LOCAL 資料交接

日期：2026-11-04（Asia/Taipei）。Base `mainline/q1q5@796cc176cd40bedbfe701b95192d3c8679755aa9`。
本次只有 safe 資料封裝／hash 與傳輸驗證，沒有 Blender、模型推論或研究實驗。
**三包已完成全檔驗證；P1 另完成 320/320 解碼像素一致及錄製／即時相容性檢查。Windows 實機仍 NOT_RUN。**

## Argon 需求盤點

先查 #416 的認領／完成／PR 狀態，再認領。依本 issue 使用者補充，檢查 #434 的 Argon issues
#419–#431、PR #435–#441 及原 #411 的 body／全部可取得留言：21 項、24 則留言。
逐項 URL／留言 URL／數量在 `d127_416_demand_sources.json`；此盤點是當下快照，不代表 PR 已採用。

| 需求 | 依據 | 本次提供／缺口 |
| --- | --- | --- |
| 核心畫面真資料／截圖 | #423，尤其 [交接留言](https://github.com/Polalalabear/amidst/issues/423#issuecomment-6628744600)；#423 本文 | 舊／新 CX-7 safe RGB、各自 run／clock／camera；P1 launcher 的本機錄製／即時已驗；完整新核心 UI 與 Windows 不冒稱驗收 |
| Colab safe pack／hash | #424、[交件](https://github.com/Polalalabear/amidst/issues/424#issuecomment-6623470425)、PR #438 | 可對兩包獨立驗證；真 Colab 解碼器／雲端執行本次 NOT_RUN，不把合成 fallback 算真結果 |
| baseline／M1–M4 真資料 | #425 本文、#427／PR #437 | 提供安全 RGB 與 provenance；正式實驗／分數／model weights 不產生也不虛構 |
| 非人物追蹤真索引 | [#422 交件](https://github.com/Polalalabear/amidst/issues/422#issuecomment-6623467023)、PR #435 | RGB 已提供；D124 正式偵測索引仍等 #417／參數核定，標 UNKNOWN，不補 fake index |
| Q4 真標註包 | #426、[交件](https://github.com/Polalalabear/amidst/issues/426#issuecomment-6623468190)、PR #436 | 可用 safe RGB 供後續出題；沒有人工 RETURN／答案／GT 進資料包，本次不做組員標註或研究驗收 |
| Windows 一鍵啟動 | #429 本文；#434 的搬檔表 | CX7_ROOT 的舊 event-viewer layout 已另投影；P1 stripped 相容啟動包及雙 manifest pins 已提供；Windows 由 #429 實測 |
| LOCAL 建檔／鏡頭設定 | #428／#409 文件包、#415 | safe camera catalog 已在兩份原 bundle 中；工具交件參照獨立 Draft #446，不混入本 PR，也不搬原 blend／private producer |
| 環境／依賴／研究圖表／清理 | #419–#422、#427–#431、PR #435–#441 | 未找到額外可合法封裝的明確 LOCAL 檔案要求；GitHub 程式由各 PR 提供，實驗／人工結果未產生保持 UNKNOWN；不刪檔／分支 |
| RT-DETR R18 權重 | #434 | 按總表從官方來源下載並驗完整 SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`（81,001,853 bytes）；本次不讀或複製本機權重 |

## 實際安全邊界

`build_argon_safe_packs.py` 僅讀三份指明 manifest 及其明列檔案；不走訪原始 run root，
不列／讀／複製 private 目錄、mutable STATE／RETURN、舊 producer、模型或原始 blend。
CX-7 路徑只讀兩份 safe_bundle；P1 路徑只讀原 MANIFEST 白名單，去 metadata 後以新 manifest／source-to-served map 綁定。

- 輸出為全新根，每檔 APFS clonefile 建立獨立 inode，拒絕 hardlink，沒有 raw-copy fallback。
  Windows 搬運後會按 logical bytes 配置空間；本機 CoW 的少量磁碟增量不是 Windows 需求量。
- copy 前後均驗來源／目標 SHA-256，來源不寫；manifest 本身含原來源 manifest pin。
- 所有 JSON／JSONL 檢查禁用資料／private locator；`gt_read` 只接受 false。
  人工靜態 `visibility_ref`（例如 `vis:A`／`static-review:*`）只是人工圖 reference，
  不接受 renderer visibility 陣列；不把引用詞當實測可見性。
- 每張 PNG 驗 RGB8 960×540、chunk 白名單、CRC、IDAT 完整性與 scanline；文字／EXIF／未知 chunk 拒絕。
- verifier 需外帶可信 manifest SHA-256，檔案集合必須精確相符，拒絕多檔、漏檔、symlink／junction、
  路徑穿越、drive path、大小寫碰撞、duplicate JSON key 與變動的 byte/hash。
- plain Python 3.12 stdlib verifier 不 import package code，不用 Blender／torch／網路。
  Windows 實機／NTFS 的執行仍 NOT_RUN，不能用 macOS 通過代替。

## 三份來源與 P1 副本

| 來源 manifest | 原 SHA-256 | 本次狀態 |
| --- | --- | --- |
| P1 v4 `MANIFEST.json` | `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` | 來源保留；依使用者追加指示只在新副本剝除 metadata，320/320 解碼像素 SHA 相同，產新 manifest |
| D119 `manifest.json` | `60f2b5f8cdddf5096ffa9a25053260568570c40d8ea2737d6663f0ae3e3c2c82` | 以原 bytes 保留在 `cx7-d119/safe_bundle/` |
| D124 `manifest.json` | `ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01` | 以原 bytes 保留在 `cx7-d124/safe_bundle/` |

P1 第一輪被 PNG metadata guard 擋下，不等於已證明有 GT。使用者隨後明確要求製作新副本。
`strip_p1_bundle.py` 只剝除 tEXt／zTXt／iTXt／eXIf，IDAT chunks 原 bytes 不改；沒有 encoder 調用。
逐張使用 Pillow 解碼原圖與新圖的 RGB bytes，320/320 pixel SHA-256 相同。
`MEDIA_TRANSFORM.json` 列出每張原 full-file hash、新 full-file hash、原／新 pixel hash、IDAT hash 與 metadata **鍵名**。
原 source manifest 原 bytes 保留在副本 `provenance/SOURCE_MANIFEST.json`，SHA 仍為 `6e9a0a4c…f1d7`。

實際移除鍵名：tEXt 的 **Camera、Date、File、Frame、RenderTime、Scene、Time**，
eXIf 的 **XResolution、YResolution**，各 320 張；未出現 zTXt／iTXt。沒有列印或保存 metadata 值。
鍵名未直接出現 GT、位置、trajectory、visibility 或 depth；File／Scene 仍可能帶來源 locator 或場景線索，
Camera／Frame 等也帶 producer context，所以全部剝除，不把 metadata 當 inference 證據。
僅憑鍵名不能證明其原值沒有劇本提示；本次不作此宣稱。

相容性保留 detection/index/clock/graph/兩份 recordings 的原 bytes 與 source RGB refs，
不把新的 served PNG hash 冒填成舊的 observation source hash。
`p1_workbench.bundle_media_reader` 從新 manifest pin 住的 transform map 與原 manifest，
同時核對原 source pin、新 served pin、完整 PNG 集合與一致 pixel pins；不匹配時 fail closed。
RGB API 的 `file_sha256` 保持原 observation source，`served_sha256` 是去 metadata 後實際送出 bytes。
原有 `public_png` 也補剝除 eXIf。新副本除 320 PNG 外，只有 bundled `p1_workbench.py` 增加必要轉接；
原 397 個 payload 中其餘 76 個 byte/hash 不變。新 MANIFEST 的 `derivation` 明列這一個 adapter override；
原 `SOURCE.json`／source_commit 留作歷史來源，不能當新 adapter 的 code pin。

新 runtime `MANIFEST.json` SHA-256：`13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805`。
新 transport `SAFE_PACK_MANIFEST.json` SHA-256：`c7f32857948468e54cdafa8d8eaaefce730c6660378191b2b2ecfe3f80dcf7fd`。
前者給 launcher；後者讓 Argon 驗完整搬運檔案集。兩者不是同一份 manifest。

`check_p1_media_compatibility.py` 對原包與副本分別跑 recorded／RULE_ONLY live，各使用全新外部 state。
status、timeline、decisions、snapshots、clock、10 次 media checks 均相同。
每次執行本來就產生不同 session refs；比對前先驗原始決策 hash，再把 session／segment／snapshot
引用按位置一對一正規化，重算這些引用派生的決策 hash；所有 time/state/observation/source 欄位原樣比較。
沒有改 source、scoring 或 controller 以通過比對。精確結果在 `d127_416_p1_compatibility.json`。

使用本 PR repo 的 `scripts/start_q1q5_p1.py` 與新 runtime pin 啟動錄製／即時模式並實際操作工作台：
- B-05b：5.10 s = A/GAP，5.15 s = B/PLAYING；gap 起點 2.50 s，原錄製 bytes 不變。
- B-05a：2.50 s = A/TEMP_LOST；5.20 s = A/RETURNED_TO_ORIGIN。live 維持 graph scope 未核時的原行為，
  **沒有**把 B-05b 的切 B 結果冒稱為 live 切 B。兩模式的 source clocks／決策時點均與原包對照一致。
- 四張 LOCAL screenshots 的路徑與 hashes 在交件 JSON；只顯示 safe RGB／系統輸出，不含 GT。
- 副本內原 legacy CLI 可單獨啟動 recorded；該舊 CLI 本來沒有 `--tracking-scope` 選項，
  live 應使用本 PR／更新 repo 的 launcher。未聲稱原 legacy CLI 具備此功能。

初次 LOCAL `/private/tmp/amidst-d127-416-delivery` 是 **未完成試產物，不可搬運**，保留失敗證據。
完成的 CX-7 產物已移至持久 artifacts 位置，沒有覆寫／刪除來源。

## Windows 交接

使用者自己搬 `cx7-d119/`、`cx7-d124/` 及同層 `verify_safe_pack.py`；不要搬原 run root。
建議放 `C:\amidst-data\d127-416`，設定：

```powershell
$env:AMIDST_SAFE_PACKS = 'C:\amidst-data\d127-416'
$env:CX7_ROOT = Join-Path $env:AMIDST_SAFE_PACKS 'cx7-d119'
$env:AMIDST_CX7_D119_BUNDLE = Join-Path $env:CX7_ROOT 'safe_bundle'
$env:AMIDST_CX7_D124_BUNDLE = Join-Path $env:AMIDST_SAFE_PACKS 'cx7-d124\safe_bundle'
```

D119 包同時保留原 safe_bundle 與從同一已 pin PNG 產出的 `A4-1/safe/media/...`／`B4-1/safe/media/...`
播放目錄，以配合現有 event-viewer／CX7_ROOT；原內容是相同 pixels，不是新渲染。
這兩種 layout 的獨立檔案都逐一列入 transport manifest，所以 Windows logical bytes 約兩份 RGB。
D124 保留新 run／clock 原 descriptors，**不**把它映射到舊 event-viewer run ID 以免錯標來源。
有新 run bytes 不代表現有 UI 已能展示；適配由 #423／#445 處理。

每包的精確大小、檔案數、transport manifest pin、Windows 驗證命令見本 PR／#416 交件通知，
並保存在 `d127_416_delivery.json`。`Get-FileHash` 只驗 manifest 本身；Python verifier 才逐檔驗全包。
P1 建議搬至 `$env:AMIDST_SAFE_PACKS\p1-v4-stripped`，設定 `$env:P1_BUNDLE` 指向該資料夾；launcher 使用上列新 runtime pin。依存 issue 仍須逐一檢查其他前置／認領／review 狀態，不能只因資料到位就聲稱 Windows 或研究已通過。
