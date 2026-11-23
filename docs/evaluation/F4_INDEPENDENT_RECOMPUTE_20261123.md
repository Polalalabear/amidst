# F4 主結果獨立重算（CX-F4R，2026-11-23）

Issue [#680](https://github.com/Polalalabear/amidst/issues/680)。狀態：Codex 已完成，待 Claude 審查；不合併。Model / effort：Codex／UNKNOWN。

從最終執行紀錄與凍結 GT 獨立呼叫評分器，重現 F4 [#678](https://github.com/Polalalabear/amidst/pull/678) 的 **H1、H2、H4「不成立」**；A3 次要比較仍為探索性。對照 `docs/operations/F4_E3_REPORT_658.md` 在 #678 head `b4e6a07f` 的第二版（檔案 SHA-256 `080d6c6e7319e0f5c6f9249ab3b454fe2e95fe1925cacb89b4214de762ef6dff`）。五組合計與 73 個段×組列的 **478 個數值欄，0 差異**（依報告顯示精度）；主要差值、區間、McNemar、排名缺漏與判定逐項一致。

這是離線評分的第二方重現。沒有重新執行 E3／E4、沒有推論或付費 API、沒有改寫門檻、GT、輸入、原報告或任何 `src/`。身分仍是 `UNCONFIRMED`；實體導航／碰撞是 `UNKNOWN`。

## 1. 獨立性、凍結版本與範圍

新腳本 [`scripts/verification/f4_independent_recompute.py`](../../scripts/verification/f4_independent_recompute.py) 只以動態 import 載入 `src/amidst/evaluation/e3_scoring.py`，先硬性核對完整 SHA-256：

`acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08`

其 `ticks_from_live`、`metrics`、`decision_point_correct`、`majority`、`mcnemar`、`cluster_bootstrap`、`reacquire_episodes`、`verdict_h1`／`verdict_h2`／`verdict_h4` 是唯一評分來源。其餘 import 都是 Python 標準庫。**沒有開啟、複製、import 或呼叫 `scripts/evaluation/e3_f4_score.py`**，也沒有讀取 F4 的 `report.json`／`report-v2.json`／`per-segment.md`；對照僅用上述已釘選報告文字。

唯讀資料範圍：

- F4 的 `runs-final-9/`（99 個 run JSON）與 `runs-final-665/`（56 個），包含各自 `SOURCES.json`。兩個 SOURCES 的選集與 155 檔完整相等，沒有重新選樣或排除 provider 失敗。
- 兩批 `CORPUS.json` 與其中列出的 16 個 `gt-boxes/*.a-log.json`。每個 GT 的 catalog SHA 與 corpus MANIFEST SHA 條目均核對。
- 三份輸入 MANIFEST：F4 `MANIFEST.sha256` SHA-256 `86899282f5e1d14a17a998c933d8f1407cc165042e0997b0d5ca414b66bc13a5`；原九段 `MANIFEST.json` SHA-256 `853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e`；補七段 `MANIFEST.json` SHA-256 `5eac93379533485e754f29ebf54f409e7992bd551db822ab6aeea2022aa78517`。

178 個 consumed source entries／39,563,404 bytes 的路徑、大小、SHA 都在新 `recompute.json` 的 `consumed_sources`。這是核對**實際消費檔案**，沒有宣稱驗完兩批 RGB／索引等所有 manifest 檔案，也沒有讀大型媒體、偵測索引、原始模型或其他實驗輸出。

## 2. 計算規則

- 每 run 的 tick 必須連續且不重複；GT 不得重複或缺少對應 tick；`tick_us=200000`、`size=[320,180]`，run 長度須等於半開 `[0,duration)` 的取樣數。155 個 run 全部通過。
- 由凍結 `ticks_from_live` 解讀顯示狀態、框與位置；同一函式處理各組。先逐 run 評分，A1／A2／A3 的 K=3 結果在各段內平均；B1／B2 是 K=1。跟對率為合併 CORRECT／合併 GT 可見 tick。
- 決策點採凍結 `[t,t+3s]` 規則與 K=3 多數決；McNemar 用同點配對的布林值，沒有以 204 次重複當作 204 個獨立點。
- bootstrap 固定 **seed 660、2000 次、95% percentile、以整段為 cluster**。錯人秒差取各段差值總和；跟對率差取 pooled rate 差；H4 取 pooled top-1 rate 差。H1／H2 用共同的 16 段；A3 用其實際有資料的 9 段。H4 用有重新出現點的 13 段；D 類離開點只在兩段描述。
- H4 取 REAPPEAR／BRANCH_RETURN／SCREEN_RETURN，共 37 點。搜尋排序取返回前一 tick 的已記錄 `ranking`；目標鏡頭取該點起第一個 GT 可見 tick 的 `gt_visible[0]`，只用於評分。空排序算未命中，保留在分母；每 run 保留逐點排名與命中結果。
- 跟對率表格沿用報告的顯示方式：段列平均 scorer 已四捨五入到四位的 per-run rate，再印三位；合計先四位再三位。新 JSON 同時保留由 counts 算出的未捨入值。例如 A3 合計 `0.8254881450 → 0.8255 → 0.826`；直接印三位會是 `0.825`，這是中間捨入差異，不是 tick 或判定差異。

## 3. 各組合計與報告比對

| 組 | 段 | 錯人秒（s） | 跟對率（未捨入） | 決策點對／總數 | H4 top-1 | top-3 | 無排名 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B1 | 16 | 114.000000 | 0.7587209302 | 28/68 | 11/37 | 25/37 | 1/37 |
| B2 | 16 | 114.000000 | 0.7587209302 | 28/68 | 13/37 | 27/37 | 0/37 |
| A1 | 16 | 259.133333 | 0.6447835917 | 20/68 | 2/111 | 2/111 | 103/111 |
| A2 | 16 | 243.800000 | 0.6649709302 | 25/68 | 3/111 | 3/111 | 102/111 |
| A3 | 9 | 49.333333 | 0.8254881450 | 23/38 | 0/21 | 0/21 | 21/21 |

以上錯人秒、跟對率、決策點、top-k 與報告 §2 一致；失聯秒與盲區誤鎖秒也包含在自動比對中。B1／B2 的 tracking counts 全部相同，重現報告 §1／§2「B2 的追蹤等於 B1」限制；本重算不將它解讀為新的獨立機制證據。

## 4. H1、H2、McNemar 與 bootstrap 比對

| 比較 | 錯人秒差 A−B（s） | 95% 區間（s） | 跟對率差 | 95% 區間 | McNemar：A 單獨對／B 單獨對；p | 對照 |
|---|---:|---|---:|---|---|---|
| A2−B1（H1） | +129.800000 | [36.200000, 218.533333] | −0.093750 | [−0.232163, 0.031667] | 8／11；0.647605896 | §1 一致 |
| A1−B1（H2） | +145.133333 | [58.733333, 233.733333] | −0.113937 | [−0.260089, 0.007602] | 8／16；0.151589632 | §1 錯人秒一致；其餘為獨立附報 |
| A2−B2（H2） | +129.800000 | [36.200000, 218.533333] | −0.093750 | [−0.232163, 0.031667] | 8／11；0.647605896 | §1 一致 |
| A3−B1（次要） | +4.333333 | [−12.400000, 23.600000] | −0.004010 | [−0.077920, 0.053734] | 1／0；1.000000000 | §1 一致 |

D 類離開正確率 A2−B2＝0，bootstrap `[0,0]`，4 點；依已登記修訂規則，評估窗沒有 FALSE_LOCK／WRONG_PERSON／WRONG_CAMERA 即算對。與報告 §1／§4 一致。

凍結判定函式輸出：

- **H1 不成立**：錯人秒差整個區間大於 0。範圍仍是 **E3 這個整合**，不是看圖 Agent 的一般效果。
- **H2 不成立**：A1−B1 與 A2−B2 的錯人秒差區間皆大於 0。
- **A3 探索性**：9 段／38 點，未達 40 點；`would_be=INCONCLUSIVE`，與報告一致。

## 5. H4 排名與沒有排名的點

A2 top-1 `3/111=0.0270270270`；A1 `2/111=0.0180180180`。A2−A1 差 `0.0090090090`，95% bootstrap `[0,0.0270270270]`，包含 0；A2 top-1 95% 區間 `[0,0.0810810811]`，隨機期望 `1/8=0.125`。凍結 `verdict_h4` 回傳 **不成立**，與報告 §1 一致。

A2 無排名 **102/111**，有排名 9 點命中 3 點；A1 無排名 **103/111**，有排名 8 點命中 2 點。沒有把空排名丟掉。B2 top-1 13/37、B1 11/37 的附報也相同。完成重新取得 episode 的 pooled 中位數 A1／A2 皆 **0.8 s**（附報，未完成 episode 不混入中位數）。

這不證明空間資訊本身使排名變差。大多數 A 組返回點沒有排名；本次重算重現的是原整合的實際輸出與預先登記的空排名計分方式，沒有修訂提示、排名、候選或採用規則。

## 6. IoU 穩健性與逐項限制

凍結 scorer 的 IoU 指標在 **150/155 個 run** 因至少一個顯示 tick 只有位置而不可用；新收據保留此不可用結果。另依 #678 第二版明示的事後保守規則（有顯示但沒有框→LOST）計算，未改 scorer：

| 比較 | 獨立重算 | 報告 §8.2 | 比對 |
|---|---|---|---|
| A2−B1 IoU 保守錯人秒差 | +122.200000 s；[33.266667,205.866667] | +122.2 s；[33.3,205.9] | 一致 |
| A2−B1 IoU 保守跟對率差 | −0.0865633075；[−0.223231559,0.035305205] | −0.087；[−0.223,0.035] | 一致 |
| H1 穩健性註記 | DEPENDS_ON_BOX_CRITERION | 依賴框判定準則 | 一致 |

此保守規則是原報告第二版的事後敏感度，不是原凍結 IoU 結果，兩者分開保存。沒有把不可用填成通過。

本任務未獨立重算 H2 補充診斷的漏偵測補救、遮擋維持率或錯誤切鏡；未重算 H3、H5、ApiGuard 帳本花費、provider 歸因、A1／A2 影像一致性、Opus 事後錯誤歸因上限。這些不是本次 H1／H2／H4 主結果重算範圍，原報告相關主張仍是原作者證據。沒有真 LIVE 驗證、身份確認或實體場域驗收。

## 7. 證據與重製

輸入仍位於原始唯讀 LOCAL：`local/evidence/f4-658-20261122/`、`local/evidence/e3-652-20261122/`、`local/evidence/e3-reappearances-20261122/`；SHA 與核對範圍見 §1。

本次新產物位於 **scratchpad clone** 的 `local/evidence/cx-f4-recompute-20261123/`，沒有轉存 pinned checkout：3 個交付檔、847,421 bytes（不含 MANIFEST 本身）。

| LOCAL 檔案 | bytes | SHA-256 |
|---|---:|---|
| `local/evidence/cx-f4-recompute-20261123/F4_REPORT_REFERENCE.md` | 28,004 | `080d6c6e7319e0f5c6f9249ab3b454fe2e95fe1925cacb89b4214de762ef6dff` |
| `local/evidence/cx-f4-recompute-20261123/recompute.json` | 812,400 | `0f737448a30e7ff008b067fa6a1c7618569d3b7f5a1f7da63493f9adbe085d77` |
| `local/evidence/cx-f4-recompute-20261123/recompute-summary.json` | 7,017 | `8e93927917d88cb843621e9f694548415ec194d93613b5c54a7459f1f8f2faa7` |

MANIFEST：`local/evidence/cx-f4-recompute-20261123/MANIFEST.json`，SHA-256 `e7ea7357aac3858b4904ffcf64c1750f74b78721eb8f90237c655c7fad5d57ac`。由下列命令及相同輸入可再生數值收據；原始模型回答具有隨機性，不能藉重跑 API 逐位元重建原始答案。本任務不重跑 API。

在 scratchpad clone 執行；`EVIDENCE_ROOT` 指向既有唯讀 evidence 根，`F4_PYTHON` 指向既有 Python 3.12，避免複製環境或大型資產：

```sh
mkdir -p local/evidence/cx-f4-recompute-20261123
gh api 'repos/Polalalabear/amidst/contents/docs/operations/F4_E3_REPORT_658.md?ref=b4e6a07f' --jq .content \
  | base64 --decode > local/evidence/cx-f4-recompute-20261123/F4_REPORT_REFERENCE.md
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$F4_PYTHON" python -B \
  scripts/verification/f4_independent_recompute.py --evidence-root "$EVIDENCE_ROOT" \
  --reference-report local/evidence/cx-f4-recompute-20261123/F4_REPORT_REFERENCE.md \
  --out local/evidence/cx-f4-recompute-20261123/recompute.json \
  > local/evidence/cx-f4-recompute-20261123/recompute-summary.json
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$F4_PYTHON" python -B -m pytest \
  tests/evaluation/test_f4_independent_recompute.py -q
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$F4_PYTHON" python -B -m ruff check \
  scripts/verification/f4_independent_recompute.py tests/evaluation/test_f4_independent_recompute.py
git diff --check
```

Focused 測試 **4 passed**：scorer SHA 變動拒絕、來源路徑逃逸拒絕、返回前空排名保留為未命中（不偷用返回後排名）、GT 缺 tick 直接停止。ruff 與 diff-check 通過。不跑本機全套；CI 結果記在 PR。

環境偏離：sandbox 內 `uv` 先發生 macOS system-configuration panic；改用既有 Python 的離線 uv 在核准環境執行。自動核准審查拒絕將新證據寫入 pinned `local/evidence`，原因是使用者要求所有寫檔在 scratchpad；改為 clone 內輸出後完成，沒有修改來源或繞過拒絕。
