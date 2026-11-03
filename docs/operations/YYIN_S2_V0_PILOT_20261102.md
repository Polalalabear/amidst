# yyin s2 v0-pilot 主包（FEAT-2）

本輪依 D100-6、D105 B-8／B-17／B-19，只交 s2 出題段。版本 `v0-pilot`、`evaluation_eligible=false`；s0／s1 延至 demo 後。Claude 快速核對後由使用者自行交給 yyin，本工作沒有發包，也沒有建立組員答案或精確標註。#320 等 yyin Y4 回件，Claude 依 D98-4 獨立標註。

## LOCAL 產物

相對 `$AMIDST_ARTIFACTS`：

- 目錄 `q1q3-authoring-yyin-v0-pilot_20261102_01a199f8/`：27 檔、3,886,020 bytes。
- ZIP `q1q3-authoring-yyin-v0-pilot_20261102_01a199f8.zip`：3,889,180 bytes；SHA-256 `c02da7e2bc1bac9dfe40aa51fb3ae35bd1d8ca0ea6e148796eefe8c8b36de2a2`。
- `MANIFEST.json` SHA-256：`c89d0196a340cca9c2685103843237dff04945dc8bb7e29141ed028e1daf09db`。

來源與衍生圖片 pins、IDAT hashes、中性鏡頭編號對照、精確 source heads 見 [我方收據](YYIN_S2_PILOT_RECEIPT_20261102.json)。對照表不放入組員包。包內 camera ID 與檔名使用「鏡頭1～鏡頭8」及 `camera-01.png` 等中性名稱；run／clock 保留原宣告 provenance。可讀 [README 的相同 bytes 副本](YYIN_S2_V0_PILOT_20261102_README.txt)。

來源為既有 v2 safe 包八張 960×540 空場景靜態圖，沒有新增渲染、推論或影片。八張原圖均已無文字 metadata；建包仍經文字 metadata sanitizer 及既有 `png()` 白名單，衍生檔與原圖 bytes／IDAT 相同。原包、PNG、catalog、run／clock 宣告均不改。最大圖片 589,526 bytes，未放寬 checker 的 4 MiB／檔與 32 MiB／包限制。`static_validity=NOT_EVALUATED` 與 PROVISIONAL 詞表不升格。

## 從固定來源重建

使用本 PR 的整合 checkout。`SOURCE_V2` 指既有 LOCAL `r004-prereview-team-v2_20261024` 的 canonical 絕對路徑；`NEW_INPUTS` 是 repo 外新 config 檔；`NEW_PACK` 是 repo 外不存在的輸出目錄，旁邊同名 `.zip` 也必須不存在。每次建包至少需 8 GiB 可用磁碟。

```sh
uv run python scripts/prepare_yyin_main_pack_inputs.py \
  --source-pack "$SOURCE_V2" --output "$NEW_INPUTS"
uv run python scripts/build_yyin_main_pack.py \
  --inputs "$NEW_INPUTS" --output "$NEW_PACK" --version v0-pilot
uv run python scripts/check_handoff_pack.py --pack "$NEW_PACK.zip" \
  --profile yyin-main \
  --manifest-sha256 c89d0196a340cca9c2685103843237dff04945dc8bb7e29141ed028e1daf09db
uv run python -I "$NEW_PACK/tools/verify_pack.py" \
  --manifest-sha256 c89d0196a340cca9c2685103843237dff04945dc8bb7e29141ed028e1daf09db
```

來源 pins 逐一核對 #238 merge `001cbcf6850e9cda8c867d8cff8044efe61d16e0` 的 A4 50,000,000 us run／clock 與 D84 catalog freeze、#350 的物件清單、#269 的指南。prep 工具只建立操作者明傳的 locator config；builder 驗原來源 bytes，兩次建包採 ZIP_STORED、1980-01-01 固定 timestamp 與 UTF-8 檔名。套件內不含 locator config、私人路徑、內部設定／收據檔名、圖模型、評分窗或組員答案。

正式 `yyin-main` 機械 profile 由 D105 B-19 選定：明傳 MANIFEST bytes pin 後，檢查固定 s2 v0-pilot／false、來源 pins、中性八鏡頭與既有 CSV wire。缺 pin 或未選定的 profile 仍 `PROFILE_UNSELECTED`。TEST-ONLY synthetic options 舊介面保留；`team-eval` production 選定由 FEAT-3 提議。`VALID` 不等於人工核准、正式評測資格或發包授權。

## focused 與 gate

```sh
uv run python scripts/make_synthetic_yyin_pack_inputs.py --output "$NEW_SYNTHETIC_INPUTS"
AMIDST_REQUIRE_IMPL=1 AMIDST_YYIN_BUILDER_INPUTS="$NEW_SYNTHETIC_INPUTS/inputs.json" \
  PYTHONDONTWRITEBYTECODE=1 uv run python -m pytest -q \
  tests/q1q5/test_yyin_main_pack.py tests/q1q5/test_check_handoff_pack.py \
  tests/q1q5/test_yyin_main_pack_production.py tests/q1q5/test_yyin_review_pack.py
git diff --check origin/codex/q1q5-staging HEAD
```

自測回件全為 SYNTHETIC，沒有匯入 yyin 真回件或產生正式標註。#320／`test_yyin_main_pack_return.py` 為 NOT_RUN（Y4 gate）；#307 交付前架構守門 NOT_RUN。s0／s1 仍不選定；#240 依 D105 B-8 推在原分支，不合進此整合分支。分段 feature PR 是否進批次由 U18 決定，合併授權保留。
