# N6 即時模式素材：r004 分件人偶、場景與光照

本功能線使用 `codex/feat-n6-live-assets`，base `main`。本次從當時最新
`origin/main@d3f032d860d97f151e58fa8864ea420b13a06af3` 開始，包含已合併 #529。
固定 demo checkout、封存 Office checkout、8785 均不作修改；所有程式在 shared scratch clone。
這是即時仿真資產；不是新的觀測、身分確認、推論輸入、研究驗收或物理安全認證。

## 骨架與動作

唯讀檢查的來源人物有 16 個獨立 mesh，沒有原生 armature、權重或連續衣物拓撲。
在記憶體中加入 17 骨、每個分件的單骨權重，以及 #529 使用的膝／肘補球。
肩 45°/75°、髖 35°/55°、膝 60°/110°、肘 70°/100° 的蒙皮矩陣探針通過。
這表示分件人偶的骨架動畫可行；不宣稱已取得寫實皮膚、衣物變形或人工自然度驗收。
無需下載替代人物，也沒有新增第三方模型授權依賴。

`character.glb` 是同一骨架人物與 `walk`、`run`、`idle` 三段動作。
全部為原地片段，沒有場景位置、錄影路線或來源 actor 的根節點運動。

| Clip | 速度 | 同腳完整 stride | 循環長度 | 支撐比例 |
| --- | --- | --- | --- | --- |
| walk | 1.2 m/s | 1.05 m | 0.875 s | 0.60 |
| run | 2.5 m/s | 1.60 m | 0.64 s | 0.38（有雙腳騰空期） |
| idle | 0 m/s | 0 m | 2 s | 雙腳固定，微幅呼吸 |

以 960 Hz 烘出骨架動畫，封裝時將時間軸校正為上表精確長度。腳步的接觸段往後移動
速度與操作者前進速度相抵；不是把固定人物平移冒充走跑。controller 在 glTF +X
方向以 1.2 / 2.5 m/s 移動，改速時以 `action.timeScale = actualSpeed / nominalSpeed` 配合。
第三人稱 WASD／Shift 控制、碰撞解算及追蹤整合留給 workbench 功能線。

`KHR_materials_variants` 提供 T / A / B / C：T 原紅上衣與原褲色、前臉／徽章／背包；
A 同紅上衣與淺灰褲；B H/S/V = 0.012/0.75/0.65、深藍褲、側包；
C H/S/V = 0.62/0.75/0.65、米色褲。HSV 依 #529 producer 的**線性 RGB**慣例。
可選配件用 variant alpha mask 顯示／隱藏。沒有把「B 的 shader H」當成逐鏡頭 RGB HSV 保證。
three.js 的載入與 variants 切換範例在 `scripts/n6_viewer/index.html`；不是修改工作台。

## 場景、比例與相機

`scene.glb` 保留 15 個實際可見 source component：牆殼、天花板、室內／室外地面、
五個屏風、車身／車艙與四輪。先評估 Blender render modifiers，包含地面與天花板
`Solidify` 厚度，才 UV unwrap、烘焙、匯出。`n6Collider=true` 節點的 mesh 就是其 collider
三角面；沒有把 AABB、隱藏 WALK proxy 或語意框當成實際碰撞幾何。
這些 collider 僅授權給本仿真展示；不擴大正式導航／推論幾何 authority。
地面與天花板的主平面採連續世界 XY UV，避免來源分件面各自展開產生的 atlas 接縫；
其餘面使用獨立保留區的 smart UV。相機矩陣轉換與回讀投影使用雙精度。

全部使用**公尺、同一原點、glTF Y-up**：Blender `(x,y,z)` → glTF `(x,z,-y)`。
角色前方向仍為 +X；Blender 左側 +Y 對應 glTF -Z。沒有重新置中或縮放場景。

`cameras.catalog.json` 保留八台原始 catalog 的內外參；`cameras.three.json` 提供轉軸後
camera-to-world、world-to-camera 及完整 projection matrix。矩陣是 row-major 巢狀陣列，
用 `THREE.Matrix4.set(...rows.flat())`，不要直接當作 three.js column-major `fromArray`。
相機看自身 -Z、自身 +Y 朝上；維持 fx/fy/cx/cy、960×540、clip planes。
`verify_n6_geometry.py` 對全部 source component 回讀比較頂點與面積，並以場景頂點
重投影核對八個鏡頭，報告在 LOCAL `verification/GEOMETRY_REPORT.json`。

## 烘焙光照與 viewer 相容性

在 Blender 5.2.1 LTS、Cycles CPU、32 samples、固定 seed 0，以同一組來源燈光／world
烘出 4096² atlas。DIFFUSE 關閉 color、保留 direct + indirect 得到線性 irradiance EXR；
COMBINED 得到 appearance，以來源 AgX / None / exposure 0 / gamma 1 輸出 RGB PNG。
人物不參與靜態烘焙，因此沒有固定人物影子。

Blender area/world 燈光不直接隨 glTF 輸出（[Blender glTF 說明](https://docs.blender.org/manual/en/5.2/addons/scene_gltf2.html)）。
本包採兩個清楚區分的通道：

- 通用 viewer：GLB 內嵌 baked appearance PNG，使用標準 `KHR_materials_unlit` baseColorTexture。
  已包含靜態光照及 AgX；renderer 用 sRGB output、NoToneMapping，不再加一次光照或 tone map。
- 需要動態 PBR 的 client：原始線性 irradiance EXR 也**內嵌在 scene GLB**，索引位於
  `asset.extras.n6Lighting.linearIrradiance.bufferView`，指定 `texCoord=1`、Linear Rec.709 float16。
  以 `parser.getDependency('bufferView', index)` 取 bytes，交 `EXRLoader.parse`。
  這是明示的 extras 契約，不冒稱標準 glTF lightmap extension。viewer 已實際解碼 EXR 驗證尺寸。
  使用此路徑時需改回未烘焙 albedo/PBR 材質；不要再把 irradiance 乘到 baked appearance 上。

`baked_appearance.png` 和 `lightmap_irradiance.exr` 的外部版本也保留供檢查；GLB 已自含它們，
載入 scene 不需額外檔案。[three.js GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html)
的標準與額外 plugin 支援不同，variants 請沿用本驗證 viewer 的明確切換函式。

光照不等於 EEVEE 影格逐像素重現：Cycles 與 EEVEE 的反射、陰影、雜訊不同，atlas 有有限
解析度／接縫，視角相關反射被固定，人物採 runtime PBR 近似。
每台相機均與 #529 A4-1 的既有第 0 幀並排；右圖為空的靜態場景，未重建錄影人物位置。
`verification/RGB_COMPARISON.json` 列出 source RGB hash、平均 RGB、display luma 差與 MAE。
這些是全畫面 sRGB8 描述統計，並非 radiometric error、人物 HSV 驗收或 GT 比分。

本次平均 display luma 差（viewer − #529，範圍 0–255）：

| 相機 | 差值 |
| --- | ---: |
| CAM_BRANCH | +11.29 |
| CAM_ENTRY | +3.73 |
| CAM_EXT_CAR | +4.75 |
| CAM_EXT_CLEAR | +3.43 |
| CAM_R101_IN | +5.75 |
| CAM_W1 | −16.14 |
| CAM_W2 | +10.86 |
| CAM_WIDE | +15.28 |

viewer 的牆／天花板較暖、陰影較平滑，W1 右側屏風面較暗；車與戶外地面的陰影較深。
主平面連續 UV 已減少接縫，部分薄細縫仍可見。這是可審查的近似外觀，並非逐像素等價。

## LOCAL 交付與查閱

所有路徑相對 `$AMIDST_ARTIFACTS`（固定為 `~/amidst/local`）：

- `data/live-assets-20261115/character.glb`
- `data/live-assets-20261115/scene.glb`
- `data/live-assets-20261115/cameras.{catalog,three}.json`
- `data/live-assets-20261115/REVIEW.html`：三動作、四變體、八鏡頭並排比較。
- `data/live-assets-20261115/MANIFEST.json`：每檔相對路徑／大小／SHA-256、Blender build、匯出設定。
- `data/live-assets-20261115/verification/SCREENSHOT_LIST.json`：23 張截圖／比較圖清單。

精確總大小、MANIFEST hash 與實際驗證數字見同 PR 的
`N6_LIVE_ASSETS_ACTUAL_20261115.json`、`N6_LIVE_ASSETS_MANIFEST_20261115.json`。
GLB、貼圖、RGB、截圖都留 LOCAL，不進 Git。
MANIFEST 的 38 個列項不含 MANIFEST 本身；其 SHA-256 另記在實際產出記錄。

本次磁碟可用空間在初始檢查約 13 GiB，最後一次 bake 開始時超過 8 GiB +512 MiB。
運算期間曾觀察到 7.6 GiB，完成後約 8.0 GiB；沒有在低水位啟動新 bake。
僅清除了本次自建且已被 shared clone 取代的重複 scratch clone（約 181 MiB），
其唯一 audit 檔與清理收據已保留。原始資料、固定 demo 與封存 checkout 都未清理。

## 重現（scratch clone，會做光照 bake，不渲染影片）

沿用同一功能分支／PR。不要在固定 demo checkout pull、切分支、改 tracked 檔或 commit。
若已存在乾淨的本功能 scratch clone，重用它。建立新 clone 的方式：

```sh
git clone --shared --no-checkout "$HOME/amidst" /private/tmp/n6-repro/clone
git -C /private/tmp/n6-repro/clone remote set-url origin https://github.com/Polalalabear/amidst.git
git -C /private/tmp/n6-repro/clone fetch origin codex/feat-n6-live-assets
git -C /private/tmp/n6-repro/clone switch --track origin/codex/feat-n6-live-assets
```

在本 PR head 的 scratch 根目錄執行。需要既有 demo Python、Blender、Chrome，以及隔離安裝
的 three.js 0.186.1 / playwright-core 1.56.1 / gltf-validator 2.0.0-dev.3.10。
不下載人物、權重或資料集。`OUT` 必須是新的輸出名字，不覆寫已有證據。

```sh
export AMIDST_ARTIFACTS="$HOME/amidst/local"
DEMO_PY="$HOME/amidst/.venv/bin/python"
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
SOURCE="$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend"
CATALOG="$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json"
OUT="$AMIDST_ARTIFACTS/data/live-assets-YYYYMMDD-repro"
N6_RUNTIME=/private/tmp/n6-repro/runtime
df -h "$AMIDST_ARTIFACTS"
# 需 free >8 GiB +512 MiB；來源 SHA 不合或輸出檔已存在會拒絕執行。
npm install --prefix "$N6_RUNTIME" --save-exact three@0.186.1 playwright-core@1.56.1 gltf-validator@2.0.0-dev.3.10

"$BLENDER" --background --factory-startup --disable-autoexec "$SOURCE" \
  --python scripts/audit_n6_character.py -- --catalog "$CATALOG" --output "$OUT/character_audit.json"
# 先查看骨架可行性報告；僅可行時往下做。
"$BLENDER" --background --factory-startup --disable-autoexec "$SOURCE" \
  --python scripts/export_n6_live_assets.py -- --repo "$PWD" --catalog "$CATALOG" --output "$OUT" --stage character
"$BLENDER" --background --factory-startup --disable-autoexec "$SOURCE" \
  --python scripts/export_n6_live_assets.py -- --repo "$PWD" --catalog "$CATALOG" --output "$OUT" --stage scene
uv run --no-project --python "$DEMO_PY" python -B scripts/package_n6_gltf.py "$OUT" --stage character
uv run --no-project --python "$DEMO_PY" python -B scripts/package_n6_gltf.py "$OUT" --stage scene
node scripts/capture_n6_viewer.mjs --assets "$OUT" --runtime "$N6_RUNTIME" --out "$OUT/verification"
"$BLENDER" --background --factory-startup --disable-autoexec "$SOURCE" \
  --python scripts/verify_n6_geometry.py -- --assets "$OUT" --catalog "$CATALOG"
node scripts/verify_n6_assets.mjs --assets "$OUT" --runtime "$N6_RUNTIME"
uv run --no-project --python "$DEMO_PY" python -B scripts/compare_n6_rgb.py \
  --assets "$OUT" --rgb-root "$AMIDST_ARTIFACTS/data/r004-4actor-natural-walk-eightcam-20261114/A4-1"
# 原始 exporter 中介 GLB 可能帶來源 preview metadata；只交付 package 後的 GLB。
mkdir "$N6_RUNTIME/producer-intermediates"
mv "$OUT/character.raw.glb" "$OUT/scene.raw.glb" "$N6_RUNTIME/producer-intermediates/"
uv run --no-project --python "$DEMO_PY" python -B scripts/manifest_n6_assets.py --assets "$OUT" --code-root "$PWD"
git diff --check
```

Blender 的 Python traceback 有時仍以 process exit 0 結束；須確認每階段收據與後續 gate
均存在且 PASS。本次 `verify_n6_assets.mjs` 強制 Khronos errors/warnings = 0，檢查動作、材質、
權重、EXR bytes、禁用欄位與 browser 數值門檻（seam <1e-5、腳滑 <0.015 m/s、接地誤差 <0.1 mm）。
驗證腳本只跑上述任務範圍，沒有 full suite、inference 或索引。

互動檢視可用同一隔離 server（啟動後列出隨機 loopback port）：

```sh
node scripts/capture_n6_viewer.mjs --assets "$OUT" --runtime "$N6_RUNTIME" --out "$OUT/verification" --serve true
```

Play loop 在原地播放，buttons 切換動作／變體，下拉選單切八鏡頭；不開啟或操作 8785。
