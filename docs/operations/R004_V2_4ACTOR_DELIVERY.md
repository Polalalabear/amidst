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
/Applications/Blender.app/Contents/MacOS/blender --background --disable-autoexec "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend" --python "$TASK_REPO/scripts/render_r004_4actor.py" -- --repo "$TASK_REPO" --scenario "$TASK_REPO/docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json" --geometry "$TASK_REPO/docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json" --catalog "$AMIDST_ARTIFACTS/data/r004-build-v2-20261021/safe_static/cameras.json" --output "$AMIDST_ARTIFACTS/data/r004-4actor-v22-20261110" --label A4-1 --authorization-ref USER_CHAT_2026-11-10_516_FULL_PIPELINE
```

B4使用同一命令的`--label B4-1`。原始輸出不存在時不能加`--resume`；已存在時只有相同source／plan／driver／appearance／code commit的LOCK才能resume。`--camera`、`--indices`、`--max-new-frames`只供有界抽樣；完整產製不帶這三項限制。

最終安全bundle、索引與LOCAL檔案逐檔SHA／數量／大小由同PR的
`docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json`提供；交件完成後在本文補上實際收據與啟動入口。
