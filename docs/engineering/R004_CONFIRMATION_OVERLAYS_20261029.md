# r004 三題靜態確認疊圖（CQ-22，2026-10-29）

三張圖供 CQ-28 #319 放進 yyin 主包 s1，尚未發包或收到答案。每題都有 A／B／C、「都不是」、「看不出來」；彩色多邊形只是待確認位置，灰色虛線是 v3_1 已有 ROI，不增加任何轉移或 authority。

- [s1-1：漏標門的位置](../history/r004_confirmation_overlays_20261029/s1-1-wide-door.svg)：A 由 PORTAL_R102 的既有靜態門洞投影；B 指右側大開口；C 指遠端位置。B／C 是固定靜態畫面上的人工定位框，不聲稱是新門洞。門指認仍 UNKNOWN。
- [s1-2：BRANCH 加深／加寬](../history/r004_confirmation_overlays_20261029/s1-2-branch-depth.svg)：A 是目前 E_CORNER_N；B 同寬延伸到 y=3.75 m；C 是畫面下緣的局部中央條帶，只指位置，不宣稱全寬可見。三個候選都不是已核准切鏡路徑。v3_1 的 E_CORNER_N 仍沒有對應轉移，及時切鏡目的未達成。
- [s1-3：WIDE 最下緣](../history/r004_confirmation_overlays_20261029/s1-3-wide-bottom.svg)：A／B／C 是同一已分類 CORR_N 支撐面的下緣左／中／右段，依影像 u 排序。下一 region／camera 仍 MISSING；回答位置不等於核准連通。

來源與完整頂點見 [curated receipt](../history/r004_confirmation_overlays_20261029/RECEIPT.json)。這是人工確認材料，不是新的 runtime schema、人工答案或 G4 收據。未讀 .blend、GT、renderer 軌跡、visibility、depth 或劇本；沒有 Blender render。

依 D97 疊在 #294 `0c34287b0b0c21c672f863fd281934f37e8aa24b`；依賴未經 Claude 複審：#294@0c34287b0b0c21c672f863fd281934f37e8aa24b。兩圖、舊 v3、scope、校正與原始 PNG bytes 都不變。

## 重現

只使用既有已去除文字／EXIF 的 960×540 無人物靜態圖。script 先驗兩張 PNG bytes pins 與 CRC／chunk 白名單；SVG 嵌入原 sanitized bytes，不重新壓縮或改像素。不要改用 HSV crop、人物影片或其他 run。

```sh
uv run python scripts/build_r004_confirmation_overlays.py \
  --provenance "$AMIDST_ARTIFACTS/r004-prereview-team-v2_20261024/provenance" \
  --static-images "$AMIDST_ARTIFACTS/r004-prereview-team-v2_20261024/images/static" \
  --output NEW_OUTPUT_DIRECTORY
```

output 必須是尚不存在的 canonical 目錄；磁碟低於8 GiB拒絕。程式固定只讀四份圖／ROI／recipe、四份 safe_static provenance、既有 portals.json 與兩張 sanitized still；逐一驗 bytes pin，幾何工作後再驗一次。來源 `.blend` 只引用既有 source SHA，不開啟原檔。

BRANCH A 與 B 各有9個靜態腳點；C 的0.4 m標記位於 CORR_N 中線，使用校正 v=518～536 px。WIDE 的三段同取 v=518～536 px，左右距支撐側邊內縮0.01 m，按影像 u 分成三段。所有6個地面候選的54足點都以 exact support 及已分類靜態射線重算；這不證明完整人體、首現邊界、物理通行或無碰撞。

初次嘗試 BRANCH 全寬的最下緣標記時，一個側邊腳點與牆相交；1 cm內縮仍有拒絕，沒有放寬見證條件。最終 C 明確採中央0.4 m局部位置標記，保留「都不是／看不出來」，由 yyin 確認需求。A／B的全寬幾何沒有因此縮小。

SVG 在瀏覽器即可開啟，圖內不連外、不含私人 locator。PNG 預覽可選用 macOS `qlmanage -t`，它只產生這些 SVG 的畫面縮圖，不是 Blender render，也不是核准證據。交付以 SVG bytes 為準，LOCAL preview不作來源依賴。

後續：CQ-28只整理這三題及指定RETURN模板，實際發包仍需U11；CQ-01／CQ-08／G4負責圖與轉移核定，本任務不代選、不修改人工原表。
