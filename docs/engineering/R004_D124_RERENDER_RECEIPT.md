# D124 A4-1／B4-1 重渲染收據（#414）

日期：2026-11-04（Asia/Taipei）。工作來源：[D124](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)、[#414](https://github.com/Polalalabear/amidst/issues/414)。
Base：`mainline/q1q5@6065cd2608be7925e4e0e98f4e4ce0d213fe5eab`，已含 #402。

**交件：兩段全量完成；真 bundle CX-7T D124 profile PASS。** 完整 hashes、原始 df 與數值見同目錄 [JSON 收據](R004_D124_RERENDER_RECEIPT.json)。
本收據只記錄新影像的 producer、safe bundle 和工程檢查；未執行 #118 偵測索引或 CX-8 真實追蹤。

## 變更與不變條件

- 僅在 Blender 記憶體中，令人物朝向跟隨當下非零 XY 行進方向；停留段保留最後朝向。沒有新增 gait，沒有平滑改寫路線或時刻。
- 增加正面臉部／胸前特徵及背包，以肉眼區分正反面；保留原紅衣材質與來源人物。
- 原 `.blend` 不儲存、不複製；原劇本 JSON 路點、凍結 JSON 與其參照不改寫。相機、960×540 RGB8、5 fps、16 samples、A4 50 s／B4 42 s 不變。
- 新朝向／外觀設定獨立放在 `configs/q1q5/producers/r004_d124_v1.json`，屬 producer 私有設定，不是 safe 或推論輸入。
- 宣告時鐘沿用原 `DECLARED_DEMO_CLOCK` 的 Asia/Taipei 映射、原點、速率及長度；新時鐘只變更 run ID、clock ID 與相應 content hash。原 repo clocks bytes 不改寫。
- 舊 LOCAL `r004-cx7-d115-20261102-01a199f8` 保留，未刪除或覆蓋。新資料使用獨立根目錄。

| 綁定 | SHA-256 |
| --- | --- |
| D124 driver `scripts/render_r004_d124.py` | `c48244be9e01915a725bf6af29b13c8a637b5f2577e4b5527da1604167d8b596` |
| D124 producer config | `b4d27b170ca4aae8537f358a6502edc662d48dc156668aa4f54be8ae88594707` |
| 原 LOCAL derived blend | `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` |
| 原 camera catalog | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| 原 `R004_A4B4_SCRIPT_FREEZE_20261029.json` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` |
| 原 A4 clock bytes | `a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a` |
| 原 B4 clock bytes | `3a39443753120c102acaf23ed7c166048157f4ae805d92ff12f36e45a31c35d4` |

## 新 run 與 LOCAL 產物

LOCAL 根目錄：`/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b`。以下相對路徑均以此為根。

| 項目 | A4-1 | B4-1 |
| --- | --- | --- |
| 新 run ID | `ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1` | `ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1` |
| 新 clock ID | `clock:r004:a4:declared-demo:v1:d124-v1` | `clock:r004:b4:declared-demo:v1:d124-v1` |
| 取樣網格 | 0…49.8 s，200000 µs 間隔 | 0…41.8 s，200000 µs 間隔 |
| 完整預期 RGB | 4 cameras × 250＝1000 張 | 5 cameras × 210＝1050 張 |
| 全量完成／實際數量 | exit 0；1000／1000 | exit 0；1050／1050 |
| 全段最低可用磁碟 | 11971829760 bytes（11.1496 GiB） | 11394543616 bytes（10.6120 GiB） |

safe 原圖位於 `<event>/safe/media/<camera>/<index:06d>.png`。文字／EXIF metadata 移除，保留原 IDAT bytes 並核對像素資料；原始臨時 PNG 每格處理後移除，不保留第二份 raw 像素副本。
`<event>/gt_private/` 保存 producer LOCK、設定／來源快照、pose journal、completion 及私有檢查；這些均不進 safe、推論、測試輸入或工作台。

完整產製後，`package_r004_d124.py` 驗證兩段 completion、2050 格 grid／hash、driver／config LOCK 與磁碟 telemetry，才建立 `bundle/safe_bundle/`。
該區只含 manifest、兩份 run descriptor、兩份新 clock、原 catalog 及 RGB；新 RGB 以 hardlink 接入同一新 run 的 safe 圖，不讀舊 run 像素。
外部 `mechanical/receipt.json` 和 `mechanical/evidence/*-inventory.json` 不在 safe bundle 內。

| 新產物 | SHA-256／結果 |
| --- | --- |
| `bundle/safe_bundle/manifest.json` | `ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01` |
| `mechanical/receipt.json` | `cc15d314fdee1dbbac66314329435a59a60321296de3bfe1095a17bcbddf6c3c` |
| `mechanical/checker.json` | PASS；`01a95fd4b1bbe0cd96c89acf9d4a40c84aab23a316d1de7aac11674b23d48791` |
| A4／B4 新 clocks、run declarations、inventories | 完整 SHA-256 見 JSON 收據 `runs` 與 checker 固定 pins |
| 唯一 inode allocated bytes | 1112563712 bytes（1.03616 GiB）；hardlink 邏輯大小不重複計入 |

## safe 視檢與 A4-c1 診斷

只檢視新 safe RGB，沒有把 private pose／GT 疊加到影像。已確認：

- LOCAL `A4-1/safe/media/CAM_W1/000089.png`（17.8 s）可見背包；`000090.png`（18.0 s）轉為正面胸前特徵，與轉身改動一致。
- LOCAL `A4-1/safe/media/CAM_W1/000125.png`（25.0 s）可辨眼部與胸前特徵。
- LOCAL `B4-1/safe/media/CAM_BRANCH/000099.png`（19.8 s）停留時可見正面，`000100.png`（20.0 s）轉向後可見背包；`B4-1/safe/media/CAM_R101_IN/000170.png`（34.0 s）可辨正面臉部／胸章。
- LOCAL `A4-1/safe/media/CAM_W1/000048.png`（9.6 s）在左側邊緣已可見部分人物。這只建立可見時間上界 **t_V ≤ 9.6 s**，未逐格排除更早出現，不能稱為精確第一格；也不是 detector observation。

[#397 §E 待查項](https://github.com/Polalalabear/amidst/pull/397#issuecomment-6620329809) 的私有靜態參考檢查使用原 D96 analytic projection 方法，明確限制 c1 的 8…11 s，七個宣告高度及 63 點 cage。
首個 selected static witness 為 **9.651833290624083 s**。這是宣告規劃線與有限參考點的靜態計算，並非 actor surface 或 RGB 實測 t_V；新 RGB 的 9.6 s 邊緣露出另列如上。
兩項證據均不支持原設計必要條件 **t_V ≥ 10.4 s**。因此將此條件記為未滿足，交評估擁有者處置；不改路線、時窗、scoring、GT authority 或既有 MISSING／UNKNOWN。
報告 `<A4-1/gt_private/c1-static-reference.json>` 留在私有區，whole-body／detector visibility 仍 UNKNOWN。

## 重現入口與 gate

以下是本任務的入口命令。兩段正式起跑 df 分別為 12527403008／11970826240 bytes（11.6671／11.1487 GiB），均 ≥9.5 GiB；supervisor monotonic elapsed 分別為 530.5636／804.0653 s，兩段 exit 0。這些是 monotonic 計時，不宣稱日曆牆鐘總耗時。使用既有 Python，不建立環境、不下載依賴。
正式渲染每段開始前 `df -k` 必須至少 **9.5 GiB＝10200547328 bytes**；執行中低於 **8 GiB＝8589934592 bytes** 即停止。driver 每格寫入另保留 frame reserve；外層 supervisor 監測該 process group。

```sh
TASK_REPO=/private/tmp/amidst-d1223-01a19f8b
TASK_RENDER_ROOT=/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b
TASK_STATIC_ROOT=/Users/polalabear/amidst-artifacts/r004-build-v2-20261021
TASK_PYTHON=/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python
df -k "$TASK_RENDER_ROOT"

/Applications/Blender.app/Contents/MacOS/blender --background \
  "$TASK_STATIC_ROOT/controlled_scene_v1_s001_r004.blend" --disable-autoexec \
  --python "$TASK_REPO/scripts/render_r004_d124.py" -- \
  --repo "$TASK_REPO" --catalog "$TASK_STATIC_ROOT/safe_static/cameras.json" \
  --config "$TASK_REPO/configs/q1q5/producers/r004_d124_v1.json" \
  --output "$TASK_RENDER_ROOT" --scenario A4-1 \
  --authorization-ref https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061 \
  --resume

uv --no-cache run --offline --no-project --python "$TASK_PYTHON" \
  python scripts/package_r004_d124.py --render-root "$TASK_RENDER_ROOT" \
  --catalog "$TASK_STATIC_ROOT/safe_static/cameras.json" \
  --config configs/q1q5/producers/r004_d124_v1.json

uv --no-cache run --offline --no-project --python "$TASK_PYTHON" \
  python scripts/check_event_run_bundle.py --profile r004-a4b4-d124 \
  --bundle "$TASK_RENDER_ROOT/bundle" \
  --receipt "$TASK_RENDER_ROOT/mechanical/receipt.json" \
  > "$TASK_RENDER_ROOT/mechanical/checker.json"
```

B4 使用同一 driver 入口及 `--scenario B4-1`；只有已存在且 LOCK 完全相符的本次輸出才能加 `--resume`。
上述 A4 已有 preview，故全量入口帶 `--resume`；沒有使用 `--camera`／`--frame-indices`／`--max-new-frames` 的全量限制。
packager 只產生 `PACKAGED_NOT_VALIDATED`，不能代替獨立 CX-7T PASS。D124 使用獨立固定 profile，不改舊 D119 pins，也不以 SYNTHETIC profile 驗真資料。

| 交件 gate | 本次結果 |
| --- | --- |
| 兩段全量／磁碟 telemetry／source 前後 hash | PASS；2050 張，來源 hash 不變，最低 10.6120 GiB |
| 真 bundle `--profile r004-a4b4-d124` | PASS；2 runs／2050 frames／2055 manifest entries |
| 相關 focused tests | 260 passed；填入實測 pins 後 D124 subset 再跑 84 passed／176 deselected |
| 架構守門 `--base origin/mainline/q1q5`，無 allow | exact head 結果登錄於 PR／#414；交件要求 0 findings |
| `git diff --check` | exact head 結果登錄於 PR／#414 |

完整 Ruff 格式檢查另有 173 項（I001 9／E402 4／E501 152／B905 7／E731 1），不是 #414 的指定 gate；名稱檢查 `ruff --select F` 為 0。已產製 driver 保持與 snapshot 精確一致，格式整理留待獨立變更，不宣稱全 Ruff 通過。

## 實際產出 / Actual output

- Model / effort: Codex；精確模型／effort UNKNOWN。
- PR / commits: 分支 `codex/414-r004-d124-rerender`；同一個 #414 Draft PR，以 PR 描述與 issue 留言記錄 exact head。Base `mainline/q1q5`；未合併。
- Files changed: D124 producer／config／focused tests、D124 bundle profile／tests、packager／tests、c1 私有參考 helper／tests、本 Markdown／JSON 收據。
- Commands run and results: 兩段全量 exit 0；package 完成；真 bundle CX-7T PASS；focused tests 260 passed，實測 pins 更新後 D124 subset 84 passed。最終無 allow 守門／diff 結果在 PR／#414。
- Artifacts: 上方 LOCAL 新 run 根、safe 視檢路徑、manifest／receipt hashes 與 1.03616 GiB 實占。GitHub 僅 code、tests、curated 收據，不上傳影像、劇本點位、pose journal 或 GT。
- Verified: 全量 safe bundle 格點、時鐘、來源與像素 hashes；2050 個 private producer 紀錄位置／切線朝向誤差均 0，停留朝向保持（A4 260／B4 520 個停留 camera-frames）。safe 視檢可區分正反面及轉身；c1 在 9.6 s 已部分露出。
- Not verified: 沒有偵測索引、推論、CX-8、重新計分、正式研究／AC7、身分、碰撞或物理可通行驗收。`human_approval_verified=false`、`allowed_purposes=[]` 不升權。
- Deviations, UNKNOWN items and follow-ups: A4-c1 原設計 t_V 必要條件未滿足，評估擁有者須處置；本任務不改路線。依 [#434](https://github.com/Polalalabear/amidst/issues/434)，#417／#418 等 #414 完成；#417 另等完整參數核定，下一個優先工作為 #412 審 #411。
