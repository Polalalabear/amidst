# Line 2 偵測改善：既有輸出的離線門檻比較（2026-10-27）

F1／[#247](https://github.com/Polalalabear/amidst/issues/247)。**PROPOSED；只執行離線 gate counterfactual，沒有偵測、渲染或 runtime 改動。** Line 1／D65／D78 參數、既有 index 和 recording bytes 均不改。

來源是 [#262](https://github.com/Polalalabear/amidst/pull/262) head `0f8be9f28e0400d7d1b060b2814677976a69d8a3` 的公開 `docs/history/p1_gap_diagnosis_20261027/summary.json`（bytes SHA-256 `495a6e6012c82b3edf45cd0846529449d394b1a653772b6b9b9d3de262884f4a`）。來源產品 `c26d7cdd07deb43c9991a4f46403ea0236277fb1`、recording `2777741d96ac9aff5bffb2f61a4d2938`，不是本次重跑產品。28 格是使用者指定失敗樣本；全 index 有 320 格，獨立可見性／正確框與 false-positive 分母 MISSING。

## 1. 三類改善方案與可計算範圍

| 類別 | 可調參數／程式提案 | 本次離線結果 | 採用前仍缺什麼 |
| --- | --- | --- | --- |
| 15 格沒有已存 person | 用獨立 index 版本比較較低 `index_score_floor`（例 0.1）；未來在 `build_detection_index` 的 floor filter 之前加預設關閉的 raw-candidate audit sink，保存官方 postprocessor top-300 的 class／score／bbox 與模型／RGB pins | 15 格都受 floor censoring；`--audit-index-floor 0.1` 回 `INCOMPLETE_RAW_BELOW_FLOOR_MISSING`，新增 person／恢復格數為 null | 該包沒有 floor 以下 raw 候選；不能在此次補造，不能將其他 class 改成 person。未來 audit sink／重新推論需另行核定與授權；top-300 postprocessor 輸出也不是完整 logits |
| 10 格分數不足 | 新的 Line 2 parameter set 比較 `link_min_score` 0.39、0.38、0.35、0.30；由離線旗標 `--link-min-score` 啟用 | 新增 score eligible 格數依序 **1、2、4、10**；0.30 共新增 11 個 eligible person observations | 這 10 格的 geometry 未納入公開診斷，完整連接、時間上界、歧義與之後歷史狀態 UNKNOWN；B123 會同時有兩個 person score eligible |
| 3 格 IoU 被拒 | 新的 Line 2 parameter set 比較 `link_iou_min`，或另案提 bounded crop/shape reference；本次只用 `--link-iou-min` 重算既有 last／D78 translation geometry | IoU 0.299／0.25／0.24／0.225 時，新通過 geometry gate 依序 **1、1、2、3** 格 | 放寬 IoU 會增加誤接風險；沒有人工正解，不能當改善率。crop/shape reference 是超出 D78 的另案契約，這次未實作 |

這三個 flag 都只屬於新 script `scripts/analyze_l2_detection_options.py`；**沒有接入產品、沒有宣稱 raw audit sink 或 crop matcher 已完成。** 不加 flag 時只分析歷史 0.4／0.3／0.5：changed gate frames = 0。`--sweep` 才列出所有比較組；預設不 sweep。未來如核准 runtime 比較，應由獨立、明示選用的 Line 2 parameter set／feature flag 開啟，省略時逐 bytes 維持原參數與輸出。

門檻權限須分清：來源錄製 `parameter.json` 的 `index_score_floor=0.3`、`link_min_score=0.4`、`query_min_score=0.5` 是 **run 級值**；來源產品 `configs/q1q5/parameter_set_v1.json` 中這三項仍是 `PROPOSED`／`value: null`。`link_iou_min=0.3`、中心距離 0.5、`link_max_gap_us=600000` 則有 APPROVED 設定。上表所有替代值都只提案，不因離線運算取得核准。`query_min_score` 不控制這 28 格的同鏡頭 linking；本次不調它。

## 2. 受影響格數與精確邊界

| opt-in 比較 | 新通過本 gate 的格 | 格數 | eligible observations／限制 |
| --- | --- | ---: | --- |
| score 0.39 | B155 | 1 | 1 |
| score 0.38 | B123、B155 | 2 | 2 |
| score 0.35 | A59、B123、B133、B155 | 4 | 5；B123 有兩個 person |
| score 0.30 | A59、A60、B123、B130、B133、B136、B138、B151、B154、B155 | 10 | 11；geometry／完整 link UNKNOWN |
| IoU 0.299 | B156 | 1 | 使用原始精度 |
| IoU 0.25 | B156 | 1 | B158 的 0.24999761356990663 仍不過 |
| IoU 0.24 | B156、B158 | 2 | 中心距離上限仍 0.5 |
| IoU 0.225 | A58、B156、B158 | 3 | A58 last 0.13709994 不過，translation 0.22535085 過 |
| score 0.30 ＋ IoU 0.225 | 上述兩組聯集 | **13** | 10 score gate＋3 geometry gate，**不是 13 個 recovered links** |
| audit floor 0.10 | 15 格的新增 person 數 UNKNOWN | null | 既有可重算 gain MISSING；不填 0 |

B156 原始 IoU 0.2990071102650908，小於 0.3；不能四捨五入成通過。此處 geometry gate 要求 **同一參照框**同時滿足 IoU 與中心距離，不把不同框的兩項最佳值湊在一起。last／translation 任一有候選只代表 geometry gate 可過；它們實際的 fallback 順序、候選排名與 ambiguity margin 仍由 linker 決定。本報告未執行 linker，也沒有把分數候選數大於 1 等同於已確認歧義。

linker 的 600 ms、同 run／clock／camera、真實觀測與歧義拒收保持；15 個無已存 person 格不畫假框、不延遲 TEMP_LOST、不插值。降門檻造成後續 reference／歷史狀態變動，不能用逐格 fixed-context 計數外推成全 session 結果。LOST 仍依 D90 只由評估端分類。

## 3. 重現與輸出

先從上述 pinned commit 匯出 **公開診斷 JSON** 到新 LOCAL 檔，不讀 RGB／raw bundle／模型。明確設定既有 Python、輸入與新的輸出路徑：

```sh
PYTHONDONTWRITEBYTECODE=1 "$EXISTING_PYTHON" scripts/analyze_l2_detection_options.py \
  --diagnosis "$LOCAL_PINNED_DIAGNOSIS" --output "$NEW_LOCAL_OUTPUT" --sweep
```

單一 opt-in：`--link-min-score 0.35`、`--link-iou-min 0.24`、`--audit-index-floor 0.10`；可合用。來源 SHA 不符、錯 recording、重複 frame、分類／分數不一致、非有限門檻、輸入變動、已存在的輸出均拒絕；不呼叫 predictor／linker／controller，不改 runtime defaults。輸出不保存 LOCAL locator。

本次產出見 [curated JSON](../history/L2_DETECTION_OFFLINE_OPTIONS_20261027.json)。它只記 source pins、方案、受影響 frame refs、限制；`recovered_links=null`、`identity_verdict=UNCONFIRMED`、formal acceptance `NOT_EVALUATED`。

程式判讀固定 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`：`src/amidst/q1q5/linker.py` SHA-256 `92d0e70e7ea15e377bfc8a604bf56133b4bf75db68b180671799b56ddaf0a33b`；`detection_index.py` SHA-256 `444f918cd5a977e2168073825bf0c33911a52e3b879d864b0ae654a5e0d8cbd2`。實際產品版本的參數與 geometry 以 #262 原 pin 為準，不以 staging 冒充來源錄製。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 本次新增 F1 Draft（head 見 PR）；來源 #262 `0f8be9f28e0400d7d1b060b2814677976a69d8a3`，staging base `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`。
- Files changed: 新增離線 script、focused tests、本文、curated JSON；產品、參數、來源輸出無改動。
- Commands run and results: `python -m pytest -q -p no:cacheprovider tests/q1q5/test_l2_detection_options.py` **13 PASS**；`python -m ruff check --select F,UP,B scripts/analyze_l2_detection_options.py tests/q1q5/test_l2_detection_options.py` PASS；`--sweep` 兩次輸出 `cmp` 相同；無旗標只有 selected baseline、changed gate=0；`git diff --check` 由提交端執行。既有 uv 的 `--no-project --offline --no-cache` 在 sandbox 的 system-configuration 產生 NULL-object panic；改呼叫既有 uv environment 的 Python，沒有安裝／新建環境。
- Artifacts: script SHA-256 `3a14937b77938dcb626518751b11cf4f9034d45159f9bb51edd1bd301cb78b5f`；tests `6f59e9b11568829d52a70b5f7637d52ef3c9403fd6a81bddd7df0947939fe326`；JSON `f454b5726191d849580b3b14f6327e6d65347fc25c917852b3fa9cdc54350dd3`。來源原包／RGB／錄製 LOCAL，未讀取或複製。
- Verified: 公開 summary bytes pin；28 格分類；各閾值 gate 精確計數；float 邊界、中心距離 guard、分數多候選與缺資料不升權；預設零 gate 變動、輸入不改、可重現 bytes。
- Not verified: 15 格 raw 分數、10 格低分候選 geometry、實際恢復連接、完整 session 重跑、recall／誤接／身份、raw sink／crop matcher 實作、模型／render／browser／AC7。
- Deviations, UNKNOWN items and follow-ups: F1 交可審查的離線方案；runtime 採用仍待契約／parameter set 核定。缺資料使 gate count 與實際品質分離，不能宣稱13格修復。
