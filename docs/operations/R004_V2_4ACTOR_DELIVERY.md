# #516 r004 四人場景產製與重現

這是來源綁定的工程產製，不是身分、導航或正式研究驗收。修正逐項見
`docs/evaluation/R004_A4B4_SCENARIO_V2_2_CODEX_FIXLOG.md`；原v2.1不覆寫。
G1報告是渲染前快照，`rendered=false` 不表示後續G2沒有渲染。

## 本機位置與隔離

`AMIDST_ROOT` 指正在服務的單一repo。只在外部scratch clone改程式；不改服務repo tracked檔或分支。
設定 `AMIDST_ARTIFACTS="$AMIDST_ROOT/local"`。新產物根相對於它為
`data/r004-4actor-v22-20261110/`；檢查證據為 `evidence/codex-516-v21-feasibility-20261110/`。
`.blend` 只讀，不能保存或複製。原run保留。

每段的 `gt_private/` 只供producer閉環，含authored plan與pose journal。
推論僅讀 `safe/` 中的RGB、來源綁定run descriptor、時計和明確HSV設定。
最終bundle不含private目錄、actor ID、authored plan、visibility或depth。
不把來源幾何或計畫路線輸入偵測、local linker、排序或重建。

## 可行性重現

使用同一個已固定的source blend（SHA-256 `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`）與catalog（`3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`）。

```sh
uv run python scripts/design/check_actor_clearance.py docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json --out "$AMIDST_ARTIFACTS/evidence/codex-516-v21-feasibility-20261110/clearance_replay.json"
uv run python scripts/design/estimate_plan_decision_points.py . docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json --variant in_band
uv run pytest tests/q1q5/test_r004_v2_516_gates.py
git diff --check
```

`build_r004_occlusion_faces.py` 從既有source mesh export的同平面真實表面union建立遮擋證明用矩形，只有`union.covers(rectangle)`才採用，不跨門洞補凸包。
`audit_r004_4actor.py` 在Blender唯讀開啟來源，clip實際mesh triangle至frustum，使用BVH找反例／凸靜態遮擋體證明整面遮蔽；未解表面維持UNKNOWN。加`--check-recording-end`會檢查所有終點，嚴於D207的錄影結束例外。B側背包包含在證明中。

`check_r004_4actor_color_proxy.py` 只計算材質×白光／world RGB假設及簡單sRGB轉換；不包含AgX、BRDF或實際crop，不能當像素觀測。G1 schema既有欄位`b_hue_measured`如實標為proxy。

## 產製入口

下面命令只在使用者授權及G1通過後執行。每次啟動前檢查`df -k ~`，至少保留8GiB＋預估1.7GiB；每格寫入另保留32MiB。進行中低於8GiB即停止。

```sh
df -k ~
/Applications/Blender.app/Contents/MacOS/blender --background --python-exit-code 1 --disable-autoexec "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend" --python "$TASK_REPO/scripts/render_r004_4actor.py" -- --repo "$TASK_REPO" --scenario "$TASK_REPO/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json" --geometry "$TASK_REPO/docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json" --catalog "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json" --output "$AMIDST_ARTIFACTS/data/r004-4actor-v22-20261110" --label A4-1 --authorization-ref USER_CHAT_2026-11-10_516_FULL_PIPELINE
```

B4使用同一命令的`--label B4-1`。原始輸出不存在時不能加`--resume`；已存在時只有相同source／plan／driver／appearance／code commit的LOCK才能resume。`--camera`、`--indices`、`--max-new-frames`只供有界抽樣；完整產製不帶這三項限制。

最終安全bundle、索引與LOCAL檔案逐檔SHA／數量／大小由同PR的
`docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json`提供；交件完成後在本文補上實際收據與啟動入口。

## 完整索引與bundle命令

以下命令讀取新run的safe資料；`TASK_REPO`為已簽出此PR產製版本的scratch clone，`TASK_PYTHON`指服務repo既有Python runtime（不建立新venv）。原始來源資料與8785服務的tracked檔案不變。

```sh
TASK_PYTHON="$AMIDST_ROOT/.venv/bin/python"
TASK_RUN="$AMIDST_ARTIFACTS/data/r004-4actor-v22-20261110"
uv --no-cache run --offline --no-project --python "$TASK_PYTHON" python -B "$TASK_REPO/scripts/prepare_r004_4actor_safe.py" --repo "$TASK_REPO" --render-root "$TASK_RUN" --catalog "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json" --baseline-config-dir "$AMIDST_ARTIFACTS/data/demo-owned-v1/metadata/config"
```

`prepare_r004_4actor_safe.py`先核對producer completion、來源／driver lock、完整格點、每張PNG hash與metadata清除結果，再以hardlink產生bundle影格。它與索引是不同程序：只有此producer closure程序可讀private完成收據；索引不接收private路徑或劇本。

從 `SAFE_PREPARED` 取得明確的safe manifest SHA，填入 `TASK_SAFE_SHA`，每個場景分別執行：

本機demo的精簡venv沒有Torch／YAML；索引命令須加 `PYTHONPATH="$AMIDST_ARTIFACTS/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps"`，唯讀重用既有D124/D131 runtime。實測Torch2.6.0／TorchVision0.21.0，未下載套件或修改服務venv。

```sh
PYTHONPATH="$AMIDST_ARTIFACTS/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps" uv --no-cache run --offline --no-project --python "$TASK_PYTHON" python -B "$TASK_REPO/scripts/index_r004_4actor.py" --safe-root "$TASK_RUN/bundle/safe" --safe-manifest-sha256 "$TASK_SAFE_SHA" --label A4-1 --model-source "$AMIDST_ARTIFACTS/data/demo-owned-v1/models/rtdetr/source/rtdetr_pytorch" --weights "$AMIDST_ARTIFACTS/data/demo-owned-v1/models/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth"
```

B4同命令改`--label B4-1`。它使用既有official RT-DETR R18、相同weights SHA、CPU FP32／seed7／threads2、stride1／score floor0.3與實際D131 HSV，不讀GT、renderer路線、visibility或depth。source Python檔逐檔hash綁定；不下載weights／依賴。每個index再跑14項既有conformance檢查與決定性RULE_ONLY local track replay。

RULE_ONLY沿用D124的`CAMERA_LOCAL_SELECTED_SEED`：每台鏡頭第一個有person的frame若非唯一候選，回`UNKNOWN_AMBIGUOUS_SEED`；不是完整多人MOT，不合併跨鏡身分。

```sh
uv --no-cache run --offline --no-project --python "$TASK_PYTHON" python -B "$TASK_REPO/scripts/package_r004_4actor.py" --artifacts-root "$AMIDST_ARTIFACTS" --safe-root "$TASK_RUN/bundle/safe" --repo "$TASK_REPO"
```

打包後會再核對所有列入檔案的大小／hash，並寫repo內的交付manifest與LOCAL `bundle/BUNDLE_MANIFEST.json`。`stage_inputs`列出safe資料的合法輸入集合；本任務實際執行detection_index與local_track。ranking與reconstruction未執行，對應清單只是可用輸入，不宣稱讀取或驗收完成。

每個產製／索引目錄都拒絕覆寫既有輸出。只對同一producer LOCK作`--resume`，不重用舊run像素。產製程式若要變更，保留舊partial run並建立新的明確來源綁定，不混合不同driver的格點。

## 讀取已完成交付

既有交付可直接讀 `bundle/safe/`，不需要重新啟動renderer。producer／index實際執行版本為
`8cc7fa6dc8eae088e845a0d3b5c51297ff0dfcfb`；此PR最終版本另補交付manifest、收據、文件與G2標記移除。
需要重現程式時，使用依本任務規則建立的scratch clone取得這個commit，不在服務repo切分支：

```sh
git clone --shared --no-checkout "$AMIDST_ROOT" "$TASK_REPO"
git -C "$TASK_REPO" remote set-url origin https://github.com/Polalalabear/amidst.git
git -C "$TASK_REPO" fetch origin codex/516-four-actor-delivery
git -C "$TASK_REPO" switch --detach 8cc7fa6dc8eae088e845a0d3b5c51297ff0dfcfb
```

原輸出已完成時不要重啟產製或索引。`--resume`只用於相同LOCK的未完成產製，不用來更新已交付的統計；新的輸入／driver需要新run與新clock綁定。
8785維持原demo pin；這份交付提供safe資料與索引，未切換工作台資料來源。前端接入與獨立人審由Claude接續。

## 實際交付（2026-11-13 記錄）

完整機械收據：`docs/engineering/R004_V2_4ACTOR_ACTUAL_RECEIPT.json`。

| 項目 | A4-1 | B4-1 |
| --- | ---: | ---: |
| RGB影格 | 1000 | 1050 |
| 模型呼叫 | 1000 | 1050 |
| render supervisor elapsed（s） | 497.01147916700575 | 757.6253203749948 |
| index elapsed（s） | 290.52920425000775 | 303.8146553340048 |
| conformance PASS結果數 | 17 | 17 |

G1/G2 12項交付關卡全PASS；指定測試檔78 passed、0 xfailed。Bundle共2,071檔，邏輯大小1,120,534,795 bytes（1.043579 GiB）；整個新run根去除hardlink重複後實占1,125,609,472 bytes。兩段render supervisor合計1254.636800s（不含pilot與暫停／日曆等待），索引合計594.343860s。渲染期間所有df／driver記錄最低可用13,128,429,568 bytes（12.226803 GiB）。

交付manifest SHA-256：`50a9806d0e4549c1c9f5159aa1a7a84058bb181da40b7c6279655e36ccf7f801`。Safe input manifest SHA-256：`1424dc86d5b8d0da1b9c9b38468398e3ef137345ba48ccbc4a093a2f13bab05a`。

RULE_ONLY共9個camera結果：7個LOCAL_SEGMENT，A4 EXT_CAR與W1為UNKNOWN_AMBIGUOUS_SEED。這些是camera-local selected-seed replay，並非完整多人追蹤或已確認身分。ranking、reconstruction、Agent評分、實際影像歧義段數與正式研究驗收未執行；5段是原工具的規劃估計。B的≥0.02紅帶餘裕仍為G1 proxy證據，未宣稱逐鏡頭實際B像素量測。
