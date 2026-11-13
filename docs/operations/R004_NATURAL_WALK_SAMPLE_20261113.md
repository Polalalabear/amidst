# #516 自然步態短樣片（2026-11-13）

使用者看完 v2.2 後要求改善人物移動的視覺。這次只改善走路姿態，保留 v2.2 路線、時刻、材質、原相機與來源 blend；另產生兩段六秒樣片，不取代 #523 的原交付。跑步、跑進房間、車旁徘徊仍是下一階段的提案。


**前次調整：使用者要求「走路屈膝小一點，大幅度留給跑步」。** 目前預設`walk`已降低抬腳與彎曲；前版設定保留為`exaggerated_reference`，只作跑步設計參考，尚未實作真正跑步的騰空期或修改速度政策。

優先看 `evidence/codex-516-natural-walk-arms-20261114/W1_arm_fix_15fps.mp4`：左為手臂修正前、右為手臂修正後；腳步／髖部逐姿態相同，兩邊同15fps、同路線／速度；`W1_natural_15fps.mp4`可單獨看新版。

**最新：手臂方向已修正，腳步保持已確認版本。**

## 觀看入口（全部 LOCAL）

下列路徑都相對於 `$AMIDST_ARTIFACTS`，也就是服務 repo 的 `local/`。媒體沒有上傳 GitHub。

- `evidence/codex-516-natural-walk-arms-20261114/REVIEW.html`：總覽入口。
- `evidence/codex-516-natural-walk-arms-20261114/W1_before_after_5fps.mp4`：W1，source t=10–16s，左右均5fps，左原版、右改善步態。
- `evidence/codex-516-natural-walk-arms-20261114/ENTRY_before_after_5fps.mp4`：ENTRY，source t=18–24s，左右均5fps；人物近鏡頭時腳部在構圖外，腳步請以W1為主。
- `evidence/codex-516-natural-walk-arms-20261114/W1_natural_15fps.mp4`、`ENTRY_natural_15fps.mp4`：各6秒、90格，較流暢的顯示樣片。沒有把原run或索引改成15fps。
- `evidence/codex-516-natural-walk-arms-20261114/BEFORE_AFTER_OVERVIEW.png`：兩鏡頭中間時刻的對照圖。

| 影片 | bytes | SHA-256 |
| --- | ---: | --- |
| W1_before_after_5fps.mp4 | 809784 | `1f089a1daaf5bbfc5bc6c9645cf2f292e152cf8767d47fece2ef49c2fba144e4` |
| W1_natural_15fps.mp4 | 457396 | `535b4bcf23ef8859d1972635db8e05d64fab876de6c8bcc7fb0b895467a1f529` |
| W1_arm_fix_15fps.mp4 | 885386 | `42f7e795424a62e8415a0592564be5a569f8d587327120cf44a43c541d99ac61` |
| ENTRY_before_after_5fps.mp4 | 313581 | `99c7074efb1031c6698e794ef605a417dc58fb19b7dfa861e85d3319ae750584` |
| ENTRY_natural_15fps.mp4 | 170423 | `2cb5757477ae9b8e3b763f18284841d731cb117f1c4a3862e29eb2348f366aa1` |
| ENTRY_arm_fix_15fps.mp4 | 311455 | `36132bc4ae39e608eb0044dbf8b11201e2a76cab91a148449b17b35b0d751f44` |

固定產物清單：`evidence/codex-516-natural-walk-arms-20261114/MANIFEST.json`，SHA-256 `bfc49d632acf620a2ebef45342d922d683c16d7a56d0316d78f28a0a517f2005`，222檔／113,094,305 bytes。包含180張最終PNG、影片、程式快照、測試與檢查收據；早期pilot資料夾與後續GitHub／結案紀錄不在此固定清單內。每個檔案的大小和SHA都在manifest中。

## 具體改動／FIXLOG

| 原行為 | 新行為 | 原因與驗證 |
| --- | --- | --- |
| 每格只平移與旋轉人物root；`new_gait_authored=false` | 行進距離決定左右腳步相位；腳抬高跨步，手臂交替擺動 | 改善整個人沿路滑行的外觀；兩連桿IK固定腿長0.40＋0.38m，腕部亦由兩連桿計算。 |
| 站姿的腳跟著root滑動 | 完整支撐階段的腳掌錨定在世界座標；起停時淡入／淡出姿態 | 聚焦測試驗證支撐腳世界位置不變、停留時姿態不持續擺動；起停過渡不宣稱全程嚴格foot lock。 |
| 第一版試格把髖部固定降低約9cm，兩膝一直彎曲 | 依兩腿的可達高度升降髖部，步幅1.05→0.95m | 目視修正蹲行感；IK不可達時報錯，不拉長肢段。 |
| 彎曲膝／肘後可看見原本分離mesh的接縫 | 記憶體內加入同材質的膝／肘接合球 | 只新增展示關節，不存來源blend；最終兩段逐格mesh表面相交檢查皆0 findings。 |
| root朝向在路點切換時直接跳到下一段方向 | 以路點前後0.16s方向做視覺朝向過渡 | 只改朝向，root位置與時刻不變；90度轉向的聚焦測試驗證連續性。急折返仍未做完整美術驗收。 |
| 最初路線比對helper以浮點秒乘1e6，32.2s端點可能超過整數末端微秒約數個ULP | helper和新sampler使用相同端點clamp | 修的是檢查helper的浮點表示問題；來源路點、原sampler、checker與關卡未改。 |


### 使用者回饋後：走路減少屈膝

| 參數／量測 | 前版大幅度 → 走路新版 | 原因與結果 |
| --- | --- | --- |
| 抬腳高度 | 0.085 → 0.018m | 降低約79%，減少抬膝像跑步的視覺。 |
| 單腿週期行進距離 | 0.95 → 0.85m | 略縮短步幅，root路線與速度不變。 |
| 支撐比例 | 0.62 → 0.55 | 保留至少一腳支撐的走路週期，減少兩腿不對稱時的額外屈膝；不是跑步騰空。 |
| 髖部額外屈曲餘量 | 0.009 → 0.001m | 讓站立腿更接近伸直，維持兩連桿可達。 |
| 擺臂／前傾 | 0.150→0.080m；0.025→0.012rad | 降低走路用力感。 |
| 平直1m/s測試最大屈膝 | 約56.8° → 33.4° | 新增測試要求<35°且較前版減少>20°；這不是所有坡度／轉彎姿態的上界。 |

`GAIT_STYLE_CHECK.json`保存兩組完整參數與量測。前版LOCAL資料夾 `evidence/codex-516-natural-walk-20261113/`原樣保留，manifest SHA `ad7e191124d1ccb8cd5eebf0fea385955ccfa92d498acfc6ec6d7597d456c0fc`；比較影片逐格核對前版PNG後再編碼。上表是新版本的修正，前面第一輪FIXLOG中的0.95m等數字屬歷史步驟。


### 2026-11-14：只修手臂，保留已確認的腳步

使用者指出手的方向相反，上下半身像在往不同方向走，明確要求腳不改。

| 原值／行為 | 新值／行為 | 原因與驗證 |
| --- | --- | --- |
| 手臂和膝蓋共用IK pole `[1,0,0]` | 手臂pole改成 `[-1,0,0]`，腿部不動 | 原前臂在人物前向+X上指向後方；改為肘部在後、手腕相對肘部朝前。 |
| 擺臂用 `-A*sin(2πphase)` | 擺臂由對側腳與同側腳的前後差驅動 | 保證左腳領先時右手領先，反之亦然；轉向後使用相同人物局部前向。 |
| 僅憑影片看腳有沒有變 | 對已確認小幅度版本逐姿態比較全部非arms欄位 | A4/B4共4,796姿態完全相同：legs、root xyz/yaw、hip height、body pitch、speed、station、weight。新增測試驗證前臂方向、手腳對側連動及90°轉身。 |

比對來源為 `evidence/codex-516-natural-walk-soft-20261113/code/scripts/r004_natural_walk.py`，SHA `c5a158c15c2ae1cedfe8f71b23d0d3e396984b3bf7f495e57bbdee78c588776c`。該版完整manifest SHA `57aba61d188a2517110dd00dd0d9e79e695f63f1a55007cff459c26554db4102`。兩個先前資料夾均保留。

`ARM_FIX_CHECK.json`及`KINEMATIC_ROUTE_CHECK.json`保存腳步不變結果。修正後手臂也適用`exaggerated_reference`參數；保留的是大幅度腿部設定，不是保留錯誤手臂方向。此參數仍不等於完整跑步模式。

模型仍是既有幾何人形，沒有更換成人類寫實模型、骨架資產或motion-capture動作。新關節只供這次producer樣片使用，不進推論、候選排序或重建。

## 本次實測與限制

- `tests/evaluation/test_r004_natural_walk.py`：10 passed，包含支撐腳不滑、固定腿長、平地腳底不穿地、停步穩定、拒絕不可達肢段、朝向連續、取樣／呼叫順序獨立與門口6cm高差的root保留。
- `KINEMATIC_ROUTE_CHECK.json`：A4/B4共4,796個姿態可解；另對上一版4,796個姿態逐項證明非手臂欄位完全相同；相對原D124 sampler的root最大位置差 `8.43769498715119e-15 m`。這是數值精度，不能當物理精度或完整場景碰撞驗收。
- W1、ENTRY各90個最終姿態：對實際render-visible牆／屏風／車體與不同人物做mesh表面相交檢查，均無相交。地面不列為牆體，以容許接觸。此檢查不等於全身各處均距牆≥0.35m，也不能檢出所有封閉體包含問題。
- 六支MP4完整decode成功：兩支原版對照各30格／5fps／6s、兩支流暢版各90格／15fps／6s、兩支手臂修正前／後比較各90格／15fps／6s。60張原始RGB與#523 bundle核對SHA／大小，另180張已採用小幅腳步的前版樣片PNG與其固定manifest核對SHA。
- 原blend SHA `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`、catalog SHA `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`保持不變；原相機matrix未動。
- 來源v2.2 SHA `14fc3a1eee450923ce799e2e6ca32adae99d8f25afc2dce7a210fb78776eef6c`。sample producer／gait的實際執行程式commit為 `9d2f8b4c4769a4486c3862a5635e3dc29d42d781`，逐檔程式SHA另在render receipts與LOCAL code快照。
- 渲染前門檻：8GiB＋350MiB預估；每格另保留32MiB。`df_before_render.txt`與`df_after_render.txt`保留原值，未觸發8GiB停止線。
- no-allow架構守門authority／inference／schemas PASS；`git diff --check` PASS。完整CI另以PR exact head結果為準。
- **未執行**RT-DETR／local track／Agent／ranking／reconstruction，沒有讀renderer GT／trajectory／visibility／depth。作者路線只供producer與數值檢查，不進上述消費端。
- **未重新驗收**全場≥0.35m肢體淨距、出生／消失視覺、實際LOST／RETURN、顏色分類或歧義段數。姿態改變仍可能影響遮擋／偵測；#523的G1/G2 PASS不能直接套用新步態。沒有改checker或#520關卡。
- 服務repo與8785未改。此次PR只供短樣片重現；等使用者看外觀再決定是否推進完整新版本與跑步／行為路線。

## 重現

使用者指定：服務repo `~/amidst` 保持原branch／tracked檔案／pin；程式在shared scratch clone中執行。以下都在scratch clone，不能在8785 checkout切分支。

前提：Blender 5.2.1、既有demo Python／Pillow／imageio-ffmpeg，來源blend與catalog仍在LOCAL。#523已交付的唯讀appearance snapshot位於 `evidence/codex-516-v21-feasibility-20261110/delivery-049f3b3c`；其 `scripts/r004_4actor_common.py` SHA `e893fd48f99e93d0d68d9eb0bbfa9f34d93abd423c26530b596531e09ff9baed`。該檔亦已發布在#523，不是隱藏的LOCAL-only程式；snapshot若遺失，從#523固定head取回相同bytes，不改用其他分支的近似版本。

```sh
export AMIDST_ARTIFACTS="$HOME/amidst/local"
export WALK_REPO=/tmp/codex-516-natural-motion-repro
git clone --shared "$HOME/amidst" "$WALK_REPO"
git -C "$WALK_REPO" remote set-url origin https://github.com/Polalalabear/amidst.git
git -C "$WALK_REPO" fetch origin codex/516-natural-walk-sample
git -C "$WALK_REPO" switch --detach origin/codex/516-natural-walk-sample
cd "$WALK_REPO"
export WALK_BASE="$AMIDST_ARTIFACTS/evidence/codex-516-v21-feasibility-20261110/delivery-049f3b3c"
export WALK_OUT="$AMIDST_ARTIFACTS/evidence/codex-516-natural-walk-arms-REPRO"
export WALK_PYTHON="$HOME/amidst/.venv/bin/python"
export WALK_FFMPEG="$HOME/amidst/.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
df -k ~
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B -m pytest tests/evaluation/test_r004_natural_walk.py -o addopts='' -q
mkdir -p "$WALK_OUT"
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B scripts/check_r004_natural_walk_routes.py --scenario "$WALK_BASE/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json" --geometry docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json --reference-gait "$AMIDST_ARTIFACTS/evidence/codex-516-natural-walk-soft-20261113/code/scripts/r004_natural_walk.py" --out "$WALK_OUT/KINEMATIC_ROUTE_CHECK.json"
```

兩個樣片分別使用下列參數；先加 `--probe-only`，確認無相交，再移除該flag產生影格。輸出路徑必須新建，producer不覆寫任何既有PNG。

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend" --python-exit-code 1 --python "$WALK_REPO/scripts/render_r004_natural_walk_sample.py" -- --repo "$WALK_REPO" --baseline-snapshot "$WALK_BASE" --scenario "$WALK_BASE/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json" --geometry "$WALK_REPO/docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json" --catalog "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json" --output "$WALK_OUT/W1" --camera CAM_W1 --start-s 10 --duration-s 6
/Applications/Blender.app/Contents/MacOS/Blender --background "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend" --python-exit-code 1 --python "$WALK_REPO/scripts/render_r004_natural_walk_sample.py" -- --repo "$WALK_REPO" --baseline-snapshot "$WALK_BASE" --scenario "$WALK_BASE/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json" --geometry "$WALK_REPO/docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json" --catalog "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json" --output "$WALK_OUT/ENTRY" --camera CAM_ENTRY --start-s 18 --duration-s 6
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B scripts/package_r004_natural_walk_sample.py --artifacts-root "$AMIDST_ARTIFACTS" --sample-root "$WALK_OUT" --ffmpeg "$WALK_FFMPEG" --previous-sample-root "$AMIDST_ARTIFACTS/evidence/codex-516-natural-walk-soft-20261113" --comparison-kind arm_fix
```

GPU／encoder／版本差異可能改變輸出bytes；以收據中的實際SHA驗證本次產物，不承諾跨機逐位元相同。重現完畢後依使用者的scratch clone規則刪除該暫存clone；保留LOCAL產物與GitHub分支。
