# #415 LOCAL 建檔與渲染工具交件

日期：2026-11-04（Asia/Taipei）。Base `mainline/q1q5@796cc176cd40bedbfe701b95192d3c8679755aa9`。
只提交程式、安全靜態相機參數與測試；未開啟原始 blend、影片、模型權重或 GT，未執行 Blender／推論。

## 指定項目與邊界

| 項目 | 本次交付 | 限制 |
| --- | --- | --- |
| `build_preview.py` | 移植 LOCAL v1 靜態建檔／匯出配方，加入 CLI、parent hash、新輸出與磁碟檢查 | 未重建 r003，未驗證 Blender 結果；新 blend 不承諾歷史 byte hash |
| `build_static_v2.py` | 移植 LOCAL v2 入口相機／光線／靜態匯出配方 | `--source-sha256` 可綁定本次 v1 衍生檔；不假設重建檔等於歷史 hash |
| `render_previews.py` | 靜態、無人物的相機預覽入口 | 舊版 45 格的人物 private preview poses **UNKNOWN，不搬、不補寫**；不宣稱重現歷史 45 格 |
| `measure_preview.py` | LOCAL 的官方 RT-DETR R18／zip、code、weights pins 與高度百分位報表，改為明確 CLI 路徑 | 本次未載入模型；0.30 僅 PROPOSED_REPORTING_ONLY；無 recall／GT 分母 |
| 舊 `render_cx7.py` | **UNKNOWN**：文件只提供 `gt_private/` 指標，沒有取得或搬入 | 使用者明令不進 private 目錄，因此未讀舊程式或其紀錄 |
| 新 `render_cx7.py` | 依使用者補充指示，從 repo freeze／收據與 safe cameras 重寫的新 producer 入口 | 不引入 #442 歷史；需要新 run ID、repo 內明確的新 clock 宣告及 byte pin、明確授權、靜態 actor prefix／前向軸／決策 reference；未渲染、未視覺驗證，不能當 #414 重驗通過 |
| D119 helper | `project_cx7_safe_bundle.py`，只讀已投影的 safe bundle 與外部已清理 inventory | 舊 helper 會讀 private inventory 且用 APFS clonefile／df；本次改用安全既有投影與獨立檔案複製，不重讀 private。無 safe 投影時不能假造 inventory |
| 鏡頭參數 | `configs/q1q5/authoring/r004_v2_static_cameras.json`，8 台原 bytes | SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；世界矩陣、lens、sensor、K／尺度／convention；`run_bindings=[]`、`NOT_EVALUATED` 保留 |

原 LOCAL 四支腳本的 byte hashes 與移植差異見 `d127_415_source_ports.json`。建檔配方中的幾何與相機座標是靜態 authoring，沒有搬人物路線或 private preview poses。
新 producer 只從 freeze pin 指定的 `producer_script` 讀取已寫在 repo 的 authored control points，
不讀評分 adapter／答案／既有渲染軌跡，也不把控制點、pose 或場景 cue 寫進 safe metadata。
凍結計畫自身的 PROPOSED 字樣不升權；程式另要求執行授權，原 freeze bytes 不變。

## 使用

六支工具都可用普通 Python 在無 Blender、無 Pillow／torch 的環境執行 `--help`。
Blender 專用工具在讀參數／授權後才 import bpy；入口支援 Blender 的 `--` 分隔。
`--execute` 和 `--authorization-ref` 只是明確執行入口，不代替使用者授權。
來源都以 pathlib 處理；拒絕 private namespace、symlink／junction、既有 output，跨平台磁碟檢查用 shutil。
Windows 實跑 **NOT_RUN**，不宣稱已驗證 Windows Blender／NTFS 行為。

只讀 repo／safe 輸入的預檢（本次測試也執行兩種 scenario）：

```sh
python scripts/render_cx7.py --scenario A4-1 --check-only
python scripts/render_cx7.py --scenario B4-1 --check-only
```

回傳 `INPUT_PINS_VERIFIED` 僅表示 freeze／plan／clock／camera bytes 對上，不代表可以渲染、
人物前向已知或 Demo 通過。前向軸缺失時 actual execution 回 `STATIC_MODEL_INPUT_REQUIRED`，不開啟 Blender/source。
新 run 的 clock 宣告必須已在 repo 且 hash、run ID、clock ID、原映射範圍皆通過檢查，保留宣告原 bytes，不能替新 run 冒填舊 declared_by／declaration_source。
前向軸與 actor prefix 必須由來源模型的靜態 authoring 核對；本次未作此核對、不從 GT 猜值。

有另外授權後的建檔入口形式（本次未執行）：

```text
blender --background --factory-startup --disable-autoexec --python scripts/build_preview.py -- --source <r003.blend> --source-sha256 <parent-pin> --output <new-v1-root> --execute --authorization-ref <ref>
blender --background --factory-startup --disable-autoexec --python scripts/build_static_v2.py -- --source <new-v1.blend> --source-sha256 <new-v1-pin> --output <new-v2-root> --execute --authorization-ref <ref>
blender --background --factory-startup --disable-autoexec --python scripts/render_cx7.py -- --scenario A4-1 --source <pinned-historical-r004-v2.blend> --output <new-run-root> --run-id <new-id> --clock <repo-new-clock.json> --clock-sha256 <pin> --actor-prefix <static-prefix> --front-axis <axis> --front-axis-ref <static-decision-ref> --execute --authorization-ref <ref>
```

事件 producer 仍固定歷史 source/catalog/freeze pins；重建出的不同 source 不能自行冒用它們。
新增眼部／胸章／背包為明列的新 authoring 視覺方案；其尺寸與實際外觀未核定、未渲染，
不可宣稱與 #442 或原 producer 的人物外觀／時刻等價。後續需要獨立靜態／短段視檢，
再由原 #414 擁有者處理；本次沒有更改它的 branch、checkout 或 review 標籤。

safe-only 投影入口需要既有 D119 來源包與清理後 evidence，沒有這些資料就停止：

```text
python scripts/project_cx7_safe_bundle.py --source-bundle <old-projection/bundle> --receipt <old-projection/receipt.json> --receipt-sha256 <pin> --output <new-root> --execute --authorization-ref <ref>
```

它先後呼叫既有 D119 checker，歷史 receipt 原 bytes 保留；本次 copy 的磁碟／hash 收據另存，
不把歷史 render 磁碟數字冒稱成今天觀測，也不變更 `human_approval_verified=false`／`allowed_purposes=[]`。
本次僅驗參數與路徑，真實包複製／checker 整合留 #416。

## 實測

`tests/q1q5/test_local_build_scripts.py`：**33 passed（0.38 s）**。
涵蓋六支工具 `python -S --help`、無授權不開來源、private／穿越／symlink／既有輸出拒絕、
8 GiB／reserve gate、source pins、兩份真 repo authored plan 的完整格數、
合成轉彎／停留／時間界線、不完整靜態人物輸入拒絕、PNG 去文字且保留 IDAT／壞 CRC 拒絕、
8 台相機原 bytes／calibration hashes／焦距換算。沒有模型或 Blender invocation。

完整 uv.lock、Windows、真實渲染／索引／人物前向與外觀、真包複製、正式研究驗收均 **NOT_RUN**。
使用既有 Python 環境透過 uv offline/no-project 執行，不宣稱完整 uv.lock 一致。
