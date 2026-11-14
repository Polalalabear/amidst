# #516 A4／B4 八鏡頭自然步態交付

這次在 main 的 #528 契約上補齊兩段各八台原始相機，採 #527 的小幅腳步與正確交叉擺臂、5 fps。v2.3 修正 A4 B／C 的出生與 C 的尾段；兩段 T 完整 actor JSON 與 v2.2 相同，事件時序不變。逐項原因與 before/after 見 [FIXLOG](../evaluation/R004_A4B4_SCENARIO_V2_3_CODEX_FIXLOG.md)。

這是工程合成資料，identity UNCONFIRMED、完整物理導航 UNKNOWN。沒有新增跑步、跑進房間、車旁徘徊、N6 或清理 F。相機圖與 8785 不在本次修改範圍，ENTRY 是否參與追蹤交由 Claude 處理。

## 來源組成與隔離

- main：`446cc7bf`（#528，八鏡頭＋v2.3 優先的關卡設定）。
- #527：`1e55272fb08dc15ff69251e3b06113c3cf12e3ba`，核定步態／Person adapter；gait SHA-256 `832f6d7c038b5874e9690a380fcadd357fcc4ae9d04240a4ce2e7f7fec846519`。
- #523：`049f3b3c2e2ea3bbcea3afdb3ab555059c6f1b85` 的 v2.2 與 appearance／安全索引工具；appearance SHA-256 `e893fd48f99e93d0d68d9eb0bbfa9f34d93abd423c26530b596531e09ff9baed`。這兩個 PR 尚未合併時，本 PR 包含所需程式依賴與來源版本，不要求切換 demo checkout。
- 原 `.blend`：`data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend`，SHA-256 `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`；只讀，不存或複製。
- 原 catalog：`data/r004-build-v2-20261021/safe_static/cameras.json`，SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；相機矩陣與 fx 不變。
- RT-DETR R18 weights：`data/demo-owned-v1/models/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth`，SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`；模型來源 `data/demo-owned-v1/models/rtdetr/source/rtdetr_pytorch`。
- D131-DEMO-HSV-v1：crop 0.50、S/V ≥0.20、red `[0.95,0.05]`；G1 的色相是明確標示的無渲染 shader/illuminant proxy，不冒稱 camera-specific RGB 實測。

所有 LOCAL 路徑相對於 `$AMIDST_ARTIFACTS`，其固定位置是 `~/amidst/local`。G1 的 authored geometry／端點／collision probe 只在 evidence；安全 bundle 不含路線、visibility、depth、GT、producer receipts。安全化只移除 PNG 文字／EXIF metadata，保留 IDAT bytes。RT-DETR 與 local tracks 僅讀 safe allowlist；ranking／reconstruction 未執行，manifest 的該兩組輸入是准許清單。

## LOCAL 產物與觀看

- 新 RGB：`data/r004-4actor-natural-walk-eightcam-20261114/{A4-1,B4-1}/CAM_*/`。A4 8×250=2,000 幀全部重產；B4 5×210=1,050 幀經來源 manifest、gait bytes、Person AST、設定與逐檔 hash 驗證後沿用 #527，另外 3×210=630 幀新產製。
- 新安全 bundle：`data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe/`，兩段全新 run／clock IDs，不讀取或混用 #523 的 records。
- G1／重產收據與 REVIEW：`evidence/codex-516-eightcam-20261114/`。每段一支八鏡頭拼接影片＋八支 960×540 單鏡頭影片，5 fps、原速；A4 50 秒、B4 42 秒。
- 精確大小、檔案數與逐檔 SHA 見同 PR 的 `R004_V2_4ACTOR_BUNDLE_MANIFEST.json` 與 `R004_EIGHT_CAMERA_FULL_MANIFEST_20261114.json`。原 #527 `data/r004-4actor-natural-walk-20261114`／`evidence/codex-516-natural-walk-full-20261114` 為凍結來源，不覆蓋。

```sh
export AMIDST_ARTIFACTS="$HOME/amidst/local"
open "$AMIDST_ARTIFACTS/evidence/codex-516-eightcam-20261114/REVIEW_FULL.html"
```

原始像素、影片、模型與完整 producer 證據留 LOCAL；GitHub 提交程式、FIXLOG、可行性報告、curated receipts、manifest 與本文件。

## 在 scratchpad 重現

不要在 `~/amidst` 或封存 checkout 改 tracked 檔、切分支或 commit。用使用者指定的 shared scratch clone，取得本 PR 的程式版本。原 demo `.venv`、Blender 5.2.1 LTS、ffmpeg 7.1 與既有 RT-DETR runtime 只讀重用，不建立環境或下載權重。

以下在本 PR checkout 的根目錄執行。`EVIDENCE`、`DATA` 必須是不存在的新名字；已凍結目錄拒絕寫入。這組命令會實際渲染，需在有效使用者授權下執行。先跑 preflight 並檢查結果；若需新路線，不覆蓋已核定的版本。

```sh
export AMIDST_ARTIFACTS="$HOME/amidst/local"
DEMO_PY="$HOME/amidst/.venv/bin/python"
SCENARIO="$PWD/docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"
EVIDENCE="$AMIDST_ARTIFACTS/evidence/codex-516-eightcam-repro-YYYYMMDD"
DATA="$AMIDST_ARTIFACTS/data/r004-4actor-natural-walk-eightcam-repro-YYYYMMDD"
FFMPEG="$HOME/amidst/.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"

uv run --no-project --python "$DEMO_PY" python -B scripts/produce_r004_natural_walk_full.py \
  --repo "$PWD" --artifacts-root "$AMIDST_ARTIFACTS" --stage preflight \
  --scenario "$SCENARIO" --evidence-root "$EVIDENCE" --data-root "$DATA"

uv run --no-project --python "$DEMO_PY" python -B scripts/prepare_r004_eight_camera_reuse.py \
  --repo "$PWD" --artifacts-root "$AMIDST_ARTIFACTS" --scenario "$SCENARIO" \
  --data-root "$DATA" --out "$EVIDENCE/REUSE_PROOF.json"

df -k ~
# 本次保守總預算 3.5 GiB，需至少 11.5 GiB；不足就停，不渲染。
uv run --no-project --python "$DEMO_PY" python -B scripts/produce_r004_natural_walk_full.py \
  --repo "$PWD" --artifacts-root "$AMIDST_ARTIFACTS" --stage render \
  --scenario "$SCENARIO" --evidence-root "$EVIDENCE" --data-root "$DATA" \
  --reuse-proof "$EVIDENCE/REUSE_PROOF.json"

# 只有兩段八鏡頭全完成才可呼叫；POSTPROCESS_LOCK 保證只啟動一次索引。
uv run --no-project --python "$DEMO_PY" python -B scripts/finish_r004_eight_camera.py \
  --repo "$PWD" --artifacts-root "$AMIDST_ARTIFACTS" --scenario "$SCENARIO" \
  --evidence-root "$EVIDENCE" --data-root "$DATA" --ffmpeg "$FFMPEG"

PYTHONPATH=src uv run --no-project --python "$DEMO_PY" python -B -m pytest \
  tests/q1q5/test_r004_v2_516_gates.py tests/evaluation/test_r004_natural_walk.py -q
git diff --check
```

完整索引輸入是 safe namespace 的新 RGB／run／clock／config／catalog；上一批 config 只提供已核定 detector／HSV／parameters，不提供 records。模型附加套件只從 `data/q1q5-dynamic-baseline-v1_20261025/runtime-deps` 讀取。若後處理某階段失敗，依其獨立 log 接續該階段，不能重跑已完成索引以冒充單次執行。

## 已驗證與限制

G1：兩段 checker 各 7/7 PASS；96 個 mesh endpoint-camera 測試 PASS，460 個全片 5 fps posed mesh 時間樣本零相交；規劃歧義 A4 3＋B4 2 段。出生／片中消失符合 D207，並對錄影末點也採更強的全鏡頭外檢查。來源 SHA、三個 clone 的 mesh 獨立性、相機矩陣／fx 不變皆有收據。

淨距指 checker 定義的人物中心對牆／家具線段 ≥0.35m，不是連續 articulated surface clearance。mesh probe 是 5 fps 表面相交抽樣，不把此結果擴大為連續碰撞／真實安全認證。歧義五段來自不變的規劃 coverage 模型，並非 RT-DETR／實際跨鏡頭身分驗收。

關卡本體維持 #528；沿用使用者先前明確授權的唯一 selftest 修正（標記計數→函式計數），交付通過後整組移除 xfail markers。PR 特別標示此例外供 Claude 逐行檢查，AST 保存證據在 LOCAL evidence。

## 實際驗收收據

- focused tests：93 passed、0 xfailed、0 failed；G1 8／G2 4 全 PASS。驗收函式本體保持 #528，只有已授權 marker selftest 例外。
- RT-DETR：A4 2,000 次、B4 1,680 次 model calls，各只跑一次；完整安全影格 3,680／3,680，逐組 IDAT 與 clock／records 範圍核對 PASS。
- 安全 bundle：3,701 檔、1,945,734,640 bytes，manifest SHA-256 `33e1b3f457381cd620e94d4beac6a2d9fba2f9203babab84b14d5ba111cbe311`。
- 完整觀看與產製固定 payload：7,587 檔、3,907,800,917 bytes，manifest SHA-256 `55aec3d9dfd443a1575692652a0646fce970ab4d203ce21b97e7fbf441e43864`。包含 3,680 個 raw PNG 及另外安全化的 PNG；檔案數／邏輯大小包含兩組，不等於新增磁碟占用。
- 兩段各 9 支影片全部解碼驗證 PASS（A4 250 幀／50 秒，B4 210 幀／42 秒），共 18 支。
- #527 凍結 payload 的 2,166 個檔案逐檔 SHA 再驗證 PASS。
- 完整摘要見 `docs/engineering/R004_EIGHT_CAMERA_ACTUAL_RECEIPT_20261114.json`；CI 最終結果與 PR head 以本 PR checks／issue 實際產出為準。
