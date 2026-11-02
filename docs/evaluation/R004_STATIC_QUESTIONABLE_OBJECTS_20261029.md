# r004 空場景可出題物件清單（CQ-26，2026-10-29）

此清單只供出題準備；不是推論輸入、正式答案或辨識率。可見程度依固定靜態圖判讀，幾何投影／射線只作交叉核對。完整＝輪廓完整入鏡；部分＝被畫面邊界截斷；看不到＝此圖未見可辨物件，不證明整個場景不存在。UNKNOWN不補成可用正例。

**建議車題來源：CAM_ENTRY（部分、左側截斷）與 CAM_EXT_CAR（完整入鏡）。** CAM_EXT_CLEAR只有最右緣極小局部，幾何可對照車元件，但獨立類別辨識UNKNOWN，預設不出車題。D74的CAM_ENTRY可供Q1，不因本清單擴大任何追蹤權限。

| camera_id | car 可見程度 | chair | dining table | 可直接放進包的車題限制 |
| --- | --- | --- | --- | --- |
| CAM_BRANCH | 看不到 | 看不到 | 看不到 | 此鏡頭不出車輛題。 |
| CAM_ENTRY | 部分 | 看不到 | 看不到 | 可自行構思車輛題；只依本張空場景圖，保留截斷限制。 |
| CAM_EXT_CAR | 完整 | 看不到 | 看不到 | 可自行構思車輛題；不保證辨識模型會命中。 |
| CAM_EXT_CLEAR | 部分 | 看不到 | 看不到 | 此鏡頭不出車輛題；右邊緣極小局部的獨立類別辨識仍UNKNOWN。 |
| CAM_R101_IN | 看不到 | 看不到 | 看不到 | 此鏡頭不出車輛題。 |
| CAM_W1 | 看不到 | 看不到 | 看不到 | 此鏡頭不出車輛題。 |
| CAM_W2 | 看不到 | 看不到 | 看不到 | 此鏡頭不出車輛題。 |
| CAM_WIDE | 看不到 | 看不到 | 看不到 | 此鏡頭不出車輛題。 |

8張空場景圖都未見可辨椅子／桌子。不要為了湊正例而把屏風、牆面、車艙或平台改標家具；實際作答仍由作答者獨立判斷。桌類詞彙沿既有 `dining table`，不新增class／alias；元件名稱本身不代替圖上判讀。

## 逐鏡頭依據

| camera_id | 圖上判讀及幾何交叉核對 |
| --- | --- |
| CAM_BRANCH | 此圖未見可辨車體；車元件樣本全部在視錐外。 |
| CAM_ENTRY | 左側可辨車體、車艙及輪，車體被畫面左邊界截斷。 |
| CAM_EXT_CAR | 車體輪廓完整入鏡，可辨車艙及輪；完整指未被畫面邊界截斷，非所有表面可見。 |
| CAM_EXT_CLEAR | 畫面最右緣只有極小車體／輪局部；由幾何可對照元件，單靠這塊影像辨識類別為UNKNOWN。 |
| CAM_R101_IN | 此圖未見可辨車體；車元件樣本全部在視錐外。 |
| CAM_W1 | 此圖未見可辨車體；車元件樣本全部在視錐外。 |
| CAM_W2 | 此圖未見可辨車體；元件樣本雖在視錐內，276個靜態射線見證均被拒絕，不能把純投影當影像可見支持。 |
| CAM_WIDE | 此圖未見可辨車體；車元件樣本全部在視錐外。 |

## 固定圖片與來源 pins

v2 MANIFEST bytes SHA-256：`531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4`。每張圖均與該MANIFEST的 `files` 相同，原始檔未改。完整24列（8台×3類）及元件footprint見[JSON清單](R004_STATIC_QUESTIONABLE_OBJECTS_20261029.json)。

| 靜態圖（LOCAL相對包根目錄） | bytes SHA-256 |
| --- | --- |
| `images/static/CAM_BRANCH.png` | `bcef1c4d56ec65a3788335eb5fae1fabdb57fa93e7694ae38614e5a668b69fc6` |
| `images/static/CAM_ENTRY.png` | `ba9ea8ce3e21ff6e42ad10e4a0fb0b2a705b5498383557989658b3f3a313fdd8` |
| `images/static/CAM_EXT_CAR.png` | `3df86031563fff471ca9637bc3aae484c9917d509a23ac7b7a45676c979ee784` |
| `images/static/CAM_EXT_CLEAR.png` | `012458b7788f928386e403b27513ac4757c5b35df11b199ef9c42ee3b5cce140` |
| `images/static/CAM_R101_IN.png` | `4076a4a019b96dbf4b36674cdc12dc72b594a2a8fcf9565968d985553b1351b0` |
| `images/static/CAM_W1.png` | `d889b861d47d897093370115c9472900b6a495b6dd0a25314766180fe674fd79` |
| `images/static/CAM_W2.png` | `20e90b35ab239a495b24b48da9b2daca059c983c72cc3bb6012c06a6fc6b29b8` |
| `images/static/CAM_WIDE.png` | `eb2e31bf0eb78696f84309b53d629e5f377756678016dae260e5d8ccb0b6b42b` |

| safe_static檔 | bytes SHA-256 |
| --- | --- |
| `provenance/source_static_geometry.json` | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| `provenance/static_membership.json` | `e71f6ad16868ab450bcd093eb50f6fd7ca4a393c73689055235e9505f9e48ca7` |
| `provenance/camera_catalog.json` | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |

有效車元件為 `R004_ENV_VEHICLE_BODY`、`R004_ENV_VEHICLE_CABIN`及四個`R004_ENV_WHEEL*`。JSON列每個元件canonical hash與世界bbox footprint，沒有複製原資產。來源校正固定8台、960×540。

## 靜態交叉核對的方法與限制

從staging `434e57922a24d2422226871c0bb672dc7bc3584b` 的既有 `r004_review_v2.py`，使用 `membership`／`triangles_for`／`project`／`static_witness`。採六個固定車元件所有頂點及各face中心，去重後276個樣本；只讀上表三份靜態provenance。使用有效靜態元件遮擋及既有2px內縮規則，不讀任何外部可見性檔。

| camera_id | FOV內樣本 /276 | 靜態射線見證 /276 |
| --- | ---: | ---: |
| CAM_BRANCH | 0 | 0 |
| CAM_ENTRY | 267 | 79 |
| CAM_EXT_CAR | 276 | 82 |
| CAM_EXT_CLEAR | 7 | 6 |
| CAM_R101_IN | 0 | 0 |
| CAM_W1 | 0 | 0 |
| CAM_W2 | 276 | 0 |
| CAM_WIDE | 0 | 0 |

這些計數不是可見面積、辨識信心或機率，有限樣本也不是完整遮擋證明。W2純視錐有276點但靜態見證為0，不能從投影推得可辨車輛；EXT_CLEAR的6個見證亦不足以把右緣小片段當獨立類別正例。

重核圖片pins（`AMIDST_ARTIFACTS`指既有LOCAL來源）：

```python
import hashlib, json, os
from pathlib import Path
root = Path(os.environ["AMIDST_ARTIFACTS"]) / "r004-prereview-team-v2_20261024"
raw = (root / "MANIFEST.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == "531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4"
manifest = json.loads(raw)
for camera in ['CAM_BRANCH', 'CAM_ENTRY', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE']:
    ref = "images/static/" + camera + ".png"
    assert hashlib.sha256((root / ref).read_bytes()).hexdigest() == manifest["files"][ref]
```

CQ-05／CQ-06與CQ-27 #317應引用這份清單及其固定head；本次沒有發包。獨立複審待Claude，未跑辨識模型或改場景。
