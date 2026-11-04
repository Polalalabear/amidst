# R004 正式索引：產製前計畫（#118；2026-11-03）

**狀態：PLAN／NOT_RUN。** 本次只規劃，沒有載入模型、讀取 RGB 像素、跑推論或建立正式索引；下列步驟不是驗收結果。

來源快照為 `mainline/q1q5@97030cd0b37240d78e832296bd6e89b5c95c018f` 與 D119 wire `49fac7121d9e52e2293c517f271fb3172d93ed65`；本分支以 merge `8b9635fb3d66a544c55b89bf53abe65aee966ae0` 接上 mainline，沒有 rebase。safe bundle 歷史產出及 hashes 見 [R004_EVENT_RUNS_RECEIPT.md](R004_EVENT_RUNS_RECEIPT.md)；本次未重新驗證 LOCAL 真資料。

## 授權與尚未成立的前置

- [D70](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6307788539) 已有 #118 正式索引的條件式授權；[D75-1](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396184028) 指定沿用 D65／§11 初值，#158 的新 HSV 比較不阻擋 baseline。這些歷史授權不會自動補完尚未物化的 run-bound 設定。
- 開跑前以 [D121](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594412627) 為準：`configs/q1q5/parameter_set_v1.json` 整體仍 `PROPOSED`、`applies_to.run_ids=[]`；D121 記錄 `run_bound_approval=UNRESOLVED`。先提出並核對 r004 正式 run 的參數綁定與核定來源，不能自行改成 APPROVED，也不改本次凍結 JSON。
- index CLI 要求已核定的 `index_score_floor`、`stride_samples`、`index_grid_origin_frame`、`hsv_config`。目前參數表的 score floor 為 null／PROPOSED，grid origin／HSVConfig 尚未以 CLI 所需形式物化；既有核定值的來源及最終 config SHA 須逐項綁定，缺項保持 UNKNOWN。
- D121 正式 Agent 組沿用既有 2000 ms／5000 ms／3 輪；探索組 11000／33000 ms 尚未核准，不執行 pilot 校準或探索組。`q3_llm_timeout_ms`／`q3_max_llm_attempts` 仍須送核定；本索引計畫不啟動 Q3／Agent，也不自行填值。下游實驗需另核對這兩項前置。
- D119 只選定 safe-bundle 機械投影。新 wire PR 的審查／合併與 #118 的 production index receipt decoder 是分別要確認的事項；safe wire PASS 不等於正式索引、CX-8、P2 或 AC7 通過。

## 固定範圍與輸入

| run | clock | 完整來源 grid（5 fps） | 鏡頭 |
| --- | --- | --- | --- |
| A4-1 `ctrl-lcorr-s1-a4-5fps-v1-r004` | `clock:r004:a4:declared-demo:v1` | 250 格／鏡頭 × 4＝1000 張；0…49.8 s | CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY、CAM_W1 |
| B4-1 `ctrl-lcorr-s1-b4-5fps-v1-r004` | `clock:r004:b4:declared-demo:v1` | 210 格／鏡頭 × 5＝1050 張；0…41.8 s | CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE |

只使用 D119 safe manifest、run descriptor、原 clock／catalog bytes 與授權 RGB；推論端不載入外部 producer inventory、GT、route、frame journal、renderer visibility／depth、事件腳本或評分窗。外部 inventory 只留在獨立機械驗證端。run／clock 分開，不能混用或用其他來源補缺。

`configs/q1q5/r004_production_v1.json` 仍是 `PROPOSED_NOT_FROZEN`，含舊 30 s 草案與空的 run 綁定，不能當正式 run 設定。50 s／42 s 與 5 fps 以已凍結來源和 D119 descriptor 為準。D121-G 的 2.5 fps S1 是後續比較，本計畫不重渲染、不改既有 5 fps 輸入。

## 執行順序（之後另案實作／產製）

1. **只讀預檢與釘源。** 重核 mainline／wire 精確 head、審查狀態、D119 checker report、safe manifest／run descriptor／clock／catalog hashes 與來源位置；核對磁碟。規劃階段不開媒體，不把歷史 2050 張 PASS 當這次重驗。
2. **先確認接口和參數。** 在 #118 登錄需要擴大的程式／測試檔案範圍；由 Claude 草擬、Codex 確認 safe-only A4/B4 adapter 與 production receipt decoder。重用既有 detection-index schema，不自行新增產品 authority 或用 SYNTHETIC 冒充真資料。run-bound 參數、detector source／weight hashes、裝置、seed、threads 與 config hash 全部列出來源後才進產製。
3. **補齊來源 adapter。** `scripts/build_q1q5_detection_index.py` 現在只接受 server-owned A/B1 registration 並硬寫 `scene_revision="r003"`，不能直接執行 A4/B4。未來需限定 D119 safe-only run 來源與 r004 provenance，重用 `src/amidst/q1q5/detection_index.py`／`hsv_color.py`；不動原 registration／來源資產，不下載模型或更換裝置。
4. **先補合成正反例。** 檢查來源/run/clock/config/hash、完整 grid、缺格、推論失敗、額外私有欄位、輸出目錄、錯誤裝置與磁碟門檻；量測 import／read／hash／forward／HSV／write 分項實際耗時。只對人工 fixture 驗證 adapter／receipt wire，交 Claude 審查。
5. **前置成立後才產製。** 先 A4、再 B4；各 run 一份 JSONL＋manifest，寫入全新 LOCAL `$AMIDST_ARTIFACTS/q1q5-r004-index-<approved-run>/<unique-batch>/`。模型／權重／CPU-FP32／seed／threads 以最後核定且重驗 hash 的組合為準；當前草案 CPU／seed 7／threads 2 不是本文件新增核定。
6. **磁碟持續守門。** 依 [D118-2](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6580320736)，開始前、每批與寫檔前量 available bytes，記錄 `df -k` 前後、最低值及新增 bytes；低於 **8 GiB（8589934592 bytes）立即停止所有本任務寫檔／推論**。保留既有產物與未完成狀態，不清理其他 clone 或來源來繼續。
7. **正式驗證與收據。** 每鏡頭 grid／coverage 精確核對；缺格或失敗保持 NOT_EVALUATED 並列原因，不推成目標不存在。以 #312 production receipt decoder（選擇項目前 UNKNOWN）、#127 索引檢查、相關 focused tests、mainline 無 allow guard 與 diff-check 驗證後，才將本文件的 PLAN 更新為實際產出；索引、權重、RGB 保持 LOCAL。

## 未來驗證入口（本次均未執行）

現有 focused 路徑為 `tests/q1q5/test_detection_index.py`、`tests/q1q5/test_hsv_color.py`、`tests/q1q5/test_check_detection_index_receipt.py`。最後一項需明確提供 #127@`e1415f32a778f497bdd048d992440718bf0a9310` 的 exact code export，不改現有 KIT_PINS。

```sh
# 以下是完成 adapter／decoder、核對所有前置之後的驗證入口。
AMIDST_INDEX_KIT_ROOT=<LOCAL exact-kit> \
AMIDST_REQUIRE_IMPL=1 PYTHONPATH=<LOCAL exact-kit>/src:src \
uv run --no-sync --offline python -m pytest -o addopts= -q \
  tests/q1q5/test_detection_index.py tests/q1q5/test_hsv_color.py \
  tests/q1q5/test_check_detection_index_receipt.py

uv run --no-sync --offline python scripts/check_architecture_guard.py \
  --base origin/mainline/q1q5 --report <NEW LOCAL report.json>
git diff --check origin/mainline/q1q5 HEAD
```

`scripts/check_detection_index_receipt.py` 目前只接受 `SYNTHETIC_TEST_ONLY_V1`；未選 decoder 仍應回 INCOMPLETE。production decoder 的參數和正式 producer 命令目前 **UNKNOWN**，因此不提供可誤執行的推論命令，也不以現有 synthetic decoder 宣稱正式 PASS。

本次實際產出只有此計畫；正式索引／參數綁定／production decoder／模型推論均 NOT_RUN。凍結 JSON、渲染輸入、#348 與 `allowed_purposes=[]` 不變。
