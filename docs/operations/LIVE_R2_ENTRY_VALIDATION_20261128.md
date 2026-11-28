# LIVE 藍衣接回與 R2 adaptive ENTRY 驗證

2026-11-28，#735、#676、#589。基線 `9f03cfc4c7519f0f76592ef0c327e08739867ea9`。定位先貼在 [#676](https://github.com/Polalalabear/amidst/issues/676#issuecomment-7231798906)。

## #676 藍衣接回

#617 留存的 H1-1 case 是紅衣操作，5 fps，73 個固定 0.05 s steps。用 `buildN6Cameras`、`hashBinding` 從 repo 場景和 N6 攝影機資料重建來源綁定，再以 `createPlayback` 重播兩次。各次 73 steps、19 個邏輯 captures，所有預期 snapshot 一致。#676 的原始 23.5 s 藍衣錄製／逐 tick 觀測仍缺，原事件的距離與拒絕分布為 `UNKNOWN`。

現行 `State._clear_target` 把 session 色交給 tracker、scheduler 與 review／lead advisor。`CameraScheduler.observe` 與 `LiveDecider` 已使用 `target_color`（#690），規則模式沒有 decider。合成 blue case 透過 #617 的錄製 API 重播兩次。後端另用凍結合成觀測重現固定 4 m gate 下的三種結果。

| 觀測 | 投影距離 | 結果 |
| --- | ---: | --- |
| 同色 | 5.0 m | `OUT_OF_GATE` |
| 異色 | 1.0 m | `COLOR_MISMATCH` |
| 同色 | 1.0 m | 接回 |

新增 HTTP 回歸以假 detector 和臨時 localhost 埠測試藍衣。正常追蹤後注入異色觀測使其失聯。23.5 s 時同色 5 m 候選在 `--relock fallback` 回 `NEEDS_CONFIRM`，`OUT_OF_GATE` 說明超出短距門檻。操作者可走既有 `reselect` 和簽章候選 `pick` 接回，後續 tick 恢復追蹤。未測量的外觀門檻依 §4.5 保持 `UNKNOWN`。

## #589 D273 操作範圍

以原有 `replay_relock.observation_records` 讀像素偵測與 capture clock，`replay_safe` 跑 `all`／`adaptive` 和 `off`／`fallback` 四種組合。`score_replays` 在全部決策完成後才接回評分欄位，沿用 `t1_analyze.mjs` 與 `entry_audit`。凍結來源沒有原先未掃鏡頭的觀測，重播保持缺值。`fallback` 的距離決策只使用標定投影。

| ENTRY 來源 | 排程、策略 | tick | CAM_ENTRY 首次排到 | 正確候選呈現延遲 | 正確自動接回延遲 |
| --- | --- | ---: | ---: | ---: | ---: |
| adaptive-A4（69 ticks） | adaptive、off | 62 | 62 | null | null |
| adaptive-A4（69 ticks） | all、fallback | 62 | 62 | 0 ms | null |
| adaptive-A4（69 ticks） | adaptive、fallback | 62 | 64 | null | null |
| all-A4（60 ticks） | adaptive、fallback | 52 | 52 | 0 ms | null |

在 69-tick 來源，adaptive＋fallback 的上一 tick 仍有配對。tick 62 先以 `ACTIVE_NEIGHBORS` 排 7 台，CAM_ENTRY 的原始觀測未進 tracker。到 tick 64 才以 `LOST_ALL` 排回 CAM_ENTRY，episode 內無合格候選呈現。保守結論為 R-4 與 R-6 的 ENTRY 掃描條件仍未通過，排程後續追蹤 [#789](https://github.com/Polalalabear/amidst/issues/789)。原始 adaptive 來源部分 ticks 只保留當時有掃的鏡頭，所以此結論限於可重播的輸入。

固定 RGB 凍結偵測的四組數值一致。A4 跟對 67/95、失聯 4/95，B4 跟對 58/60、失聯 1/60，符合 R-6 的率門檻。原 D273 收據的四組協定違規皆 0，本次凍結重播沒有重新量測 A→B 協定違規。另跑 protocol／HUD 測試驗證 `NEEDS_CONFIRM`、候選形狀和 GT 隔離。

本批交付驗證工具與回歸。`--relock off` 是 runtime 預設，#589 仍等 adaptive ENTRY 後續與門檻／回退核定；紅衣 production 路徑維持原樣。#675 等 E8 結論。

## 重跑

在獨立 clone 以既有唯讀 Python 與 Node 相依執行。`EVIDENCE`／`DATA` 指定專案的 LOCAL 根，`AMIDST_ARTIFACTS` 指定輸出根。使用新輸出路徑。

```sh
node --test frontend/live-mode/test/recording.test.mjs frontend/live-mode/test/protocol.test.mjs frontend/live-mode/test/hud.test.mjs
node scripts/verification/live_blue_recording.mjs > "$AMIDST_ARTIFACTS/blue-recording.json"
PYTHONPATH=src "$PYTHON" -B scripts/verification/live_color_gate_diagnose.py --out "$AMIDST_ARTIFACTS/blue-gate.json"
PYTHONPATH=src "$PYTHON" -B scripts/live_mode/verify_relock_r2.py --d273 "$EVIDENCE/cx552-d-20261118" --cameras "$DATA/live-assets-20261115/cameras.catalog.json" --out "$AMIDST_ARTIFACTS/run"
PYTHONPATH=src "$PYTHON" -B -m pytest -q -o addopts= -p no:cacheprovider tests/live_mode/test_track_endpoints.py tests/live_mode/test_session_target_color.py tests/live_mode/test_server_relock.py tests/live_mode/test_relock_replay.py
git diff --check
```

Python 41 passed，Node 59 passed。R2 驗證獨立執行兩次，`summary.json` 逐 bytes 相同。USD 0，實際模型呼叫 0。

## LOCAL 來源與產物

| 路徑 | 大小／檔數 | SHA-256 | 重建 |
| --- | ---: | --- | --- |
| `local/evidence/cx617-main-20261120/a/browser.case.json` | 152,561 bytes／1 | `9aace10a7b99114f48958d1576b7c6549543a3085baf0b560d516e9402e8fe09` | 歷史錄製，位元組無法重建 |
| `local/evidence/cx552-d-20261118/MANIFEST.json` | 13,559 bytes，涵蓋 80 檔 | `803e6e09ade8ab128f9e7387e42cf568127858832335892389aff7348f507090` | 歷史凍結來源，D273 文件說明可重跑範圍 |
| `local/data/live-assets-20261115/cameras.catalog.json` | 12,793 bytes／1 | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` | 凍結校正，直接讀取 |
| `$AMIDST_ARTIFACTS/run/summary.json` | 12,667 bytes／1 | `768b1d2513b31e7d3a972954a63b252b879f5d5b4058686a64cbae292972ec30` | 以 `verify_relock_r2.py` 重建，含四份輸入及 graph 校驗值 |
| `$AMIDST_ARTIFACTS/blue-recording.json` | 187,532 bytes／1 | `47f12976e07717ad160effef8a95706455bb7bf242db18f9e808c5e9d2a2a427` | 以 `live_blue_recording.mjs` 重建 |
| `$AMIDST_ARTIFACTS/blue-gate.json` | 8,769 bytes／1 | `1585d809e50725633d30bd765addf66630cbacc3e04f77d33631feeae6fac833` | 以 `live_color_gate_diagnose.py` 重建 |

要核對 #617 原 H1-1 檔案的兩次輸入重播，在同一 clone 使用下列指令。這段只進行模擬步進，沒有相機擷取或 detector。

```sh
node --input-type=module - "$EVIDENCE/cx617-main-20261120/a/browser.case.json" "$DATA/live-assets-20261115/cameras.three.json" <<'JS'
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createCrowd} from './frontend/live-mode/src/crowd.mjs';
import {buildN6Cameras} from './frontend/live-mode/src/n6.mjs';
import {captureStride, createPlayback, hashBinding} from './frontend/live-mode/src/recording.mjs';
import {Scene} from './frontend/live-mode/node_modules/three/build/three.module.js';
const read = path => JSON.parse(fs.readFileSync(path));
const source = read(process.argv[2]);
const cameraSource = read(process.argv[3]);
const geometry = read('docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json');
const scenario = read('docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json');
const run = scenario.runs.find(r => r.run_id === source.run_id);
const segments = geometry.clearance_segments;
const scene = new Scene();
const cams = buildN6Cameras(cameraSource, scene, source.config.w, source.config.h);
scene.updateMatrixWorld(true);
const bindings = {
  scene_sha256: await hashBinding({run, segments}),
  cameras_sha256: await hashBinding(Object.fromEntries(Object.entries(cams).map(([id, {camera}]) =>
    [id, {world: camera.matrixWorld.toArray(), projection: camera.projectionMatrix.toArray()}]))),
};
assert.deepEqual(bindings, source.bindings);
for (let i = 0; i < 2; i++) {
  const crowd = createCrowd(run, {actorId: source.actor_id, segments, auto: !!source.config.auto, cfg: source.config.crowd, strict: false});
  const playback = createPlayback(source, crowd, bindings);
  while (!playback.done) playback.step();
}
console.log(JSON.stringify({recorded_case: source.case_id, repeats: 2, steps_per_replay: source.inputs.length,
  logical_captures_per_replay: 1 + Math.floor(source.inputs.length / captureStride(source.config.fps)), bindings, exact_expected_snapshots: true}));
JS
```
