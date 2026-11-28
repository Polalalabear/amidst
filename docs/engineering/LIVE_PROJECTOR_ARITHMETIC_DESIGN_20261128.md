# #795 LIVE 投影算術與凍結證據相容性設計

2026-11-28。D415 設計待 Claude 審查。檢查基線 `7dbd2ac084600a86b03710cb9eedd6647667c078`，E8 對照 `#785@f6f70f7cb361da6009893a5f40af0e1ddadf2649`。[#795](https://github.com/Polalalabear/amidst/issues/795) · [D421](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7236153587)

## 投影誤差的來源

在 [`Projector.ground`](../../src/amidst/live_mode/tracker.py) 中，bbox 腳點先依影格尺寸轉回標定像素，再由內參生成相機射線。NumPy 的 `M[:3, :3] @ d_cam` 依平台的矩陣乘法路徑選擇加總順序及融合乘加。射線尾位差異可以傳到與 `z=0` 平面的交點和 `est_xy`。當追蹤狀態、鏡頭、bbox 及時鐘均相同，完整追蹤欄位的零容忍比較仍會失敗。未量測的極端案例可能碰到門檻或排序 tie。

原 E8 Colab 有 **25/28** 案例在 G1/V2 停住。離散欄位差異為 0，`est_xy` 最大差異 `3.553e-15`。#785 在 Part 2 notebook 先覆寫 `ground_ieee`，B1 與後續各組共用固定從左到右的算術，保留 `rows[].tracking` 的精確比較。現行 G1 用 Python 欄位等值與列數比對，無容差。#785 回報 Mac gate 28/28、34,247 筆投影等同 Mac NumPy，以及 685 筆 arm64／Rosetta 投影等同；真實 Colab 全 28 案的修正後 gate 仍待驗證。[`e8_colab_run.py` gate](https://github.com/Polalalabear/amidst/blob/f6f70f7cb361da6009893a5f40af0e1ddadf2649/src/amidst/evaluation/e8_colab_run.py#L164-L172) · [#780 原始停點與修正證據](https://github.com/Polalalabear/amidst/issues/780#issuecomment-7236184363)

## #773／D419 的 B-05 封存

只讀核對兩份 17,133-byte 回應與 manifest，逐欄差異共 **37 個字串**，是 10 個參數雜湊、26 個追蹤引用、1 個輸出雜湊。兩份 `display_estimate` 相同，均為 `CALIBRATION_MISSING`，該路徑在建構 `Projector` 前已返回。兩組 `single_view`、`multi_view`、觀測與時鐘相同。將 P1 v4 參數的 `agent_call_timeout_ms` 由 2,000 改為 8,000，`agent_total_budget_ms` 由 5,000 改為 24,000，以及兩列的提案來源標為 D313，即重現 gate r5 的參數雜湊。替換四組一致映射的 `track_ref` 後，可重現完整 gate r5 回應與輸出雜湊。B-05 維持 D419 判準。現場同 session 重送仍為 `UNKNOWN`。 [#773 封存與完整 SHA](../operations/AC7_B05_TRACK_HASH_20261127.md) · [D419](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7225266557)

| B-05 封存 | 參數 SHA 前綴 | 回應 SHA 前綴 |
| --- | --- | --- |
| 8785 AC-720 | `3d3067f5` | `fb2dc77e` |
| gate r5 | `c1d63e2a` | `b2b86626` |

## 影響面與釘選處理

| 消費者 | 哪些值會受影響 | 後續驗證與釘選 |
| --- | --- | --- |
| LIVE `State`、凍結 D273/R2 重播 | [`server.py`](../../src/amidst/live_mode/server.py)、[`replay_relock.py`](../../scripts/live_mode/replay_relock.py) 共用投影。數值會進 `tracking.est_xy`、診斷、距離 gate 與候選。 | 比較完整追蹤欄位、狀態與事件，再產生新候選 runtime 的 code SHA 和結果 manifest。歷史 D273／#790／#794 收據隨原 runtime 重跑。 |
| E3／E5／E6／E7 | [E3 baseline](../../scripts/evaluation/e3_cases/baseline.py) 將 `tracker.py` SHA 寫入 `source.files`，整份進 `snapshot_sha256`。已登錄的 [E3 config](../../configs/evaluation/e3_live_cases_v1.json) 使用 `6e06b122…75ae0`。[`e5_run.py`](../../scripts/evaluation/e5_run.py) 記 runtime source SHA，[`e6_rule_neutral.py`](../../scripts/evaluation/e6_rule_neutral.py)、[`e7_replay_run.py`](../../scripts/evaluation/e7_replay_run.py) 也建 `Projector`。 | 既有正式結果、b-logs、快照、實驗 manifest 與 source pins 以歷史 commit 重現。未來採新 runtime 的實驗另建新世代收據。E6 正式流程的 freeze 驗證還綁定 clean HEAD，新 E6 執行才重建該收據。E7 已產出的模型 checkpoints 與只用偵測盒的 request pack 可繼續使用，新 E7 追蹤重播另記 runtime SHA 與輸出 SHA。來源 RGB、偵測索引、標定與圖的相同位元組沿用原 SHA。 |
| E8 Part 1／Part 2 | Part 1 讀凍結 B1 快照，L2 投影距離與已產生請求隨 pack 固定。打包器也為 Part 2 從偵測盒產生三位小數的 `ground_xy`，`PACK_INFO.json` 綁定來源 commit。Part 2 的 G1 比每個案的 `rows[].tracking`，任一案失敗會停。 | 既有 [#785](https://github.com/Polalalabear/amidst/pull/785) 的 notebook override、pack、manifest、ZIP SHA、已存 checkpoints 與停點紀錄維持同一世代。遷移到 src 時，先用**同一份**凍結 b-logs 在 Mac、native Linux x86_64 及實際 Colab 驗證完整 28/28。遷移版登記新 notebook code pin 和 checkpoint namespace（fingerprint 同時綁 code SHA 與 pack manifest）。若用新 src 重打包，再產生新 pack metadata、manifest、ZIP 與 Mac index SHA。保持 D421 的精確 gate。 |
| 8785 AC7 與 gate r5 | [`Demo.with_estimate`](../../scripts/serve_demo_integration.py) 會把 [`demo_estimate.py`](../../scripts/demo_estimate.py) 的數值 `display_estimate` 納入 canonical `output_sha256`。A4-1／B4-1 與已綁定標定的 8CAM 路徑會用到同一投影器。既有 A4-1／B4-1 的座標與雜湊在兩份封存一致（`bcc36032…`、`bc921cfe…`）。 | 歷史 `5727fc9a` pin、B-05 D419、gate r5 manifests 供原樣重現。新候選先在獨立環境比 exact estimate 與 `output_sha256`，並驗 AC7 的視角與參數條件。若經審查接受新回應位元組，為候選重建 gate 收據，再依既有流程核准換 pin。 |

## 提議的最小 src 變更與驗收

1. 在 `src/amidst/live_mode/tracker.py` 內沿用 D421 的純量計算。保留像素縮放順序、座標軸符號、`d_z >= -1e-6`、`t <= 0`、`t > 80` 與現有回傳格式。射線的 `x0`、`x1` 先按現有輸入精度完成縮放與內參換算，再轉 built-in `float`，維持舊 NumPy float64 射線的進入乘法精度。每列按 `(r0*x0 + r1*x1) + r2*x2` 左結合，交點用個別純量乘與加。固定運算順序，不引入座標捨入或放寬下游閘門。保留 `cams` 介面，先量測再決定是否需快取矩陣純量。
2. 新增 focused 投影回歸，保留同一組 IEEE binary64 輸出 golden，在 Mac arm64 和 native Linux x86_64 明確執行。現有 clean-clone 檢查沒有跑這組測試。含兩種解析度、取消誤差、負零與 valid／`None`，及 `d_z=-1e-6`、`t=0`、`t=80` 前後相鄰值。另測 `np.float32` bbox 的 cast 時機。現有 `finite_point` 接受 Real，NumPy 2 下若把 notebook 寫法直接移入並保留 float32 射線乘法，合成案例已看到與舊 projector 不同的結果。
3. 逐位元比對舊 Mac 與候選的原定凍結 B1、D273/R2 追蹤欄位及歷史 8785 校正案例。單純數值比對之外，列狀態、鏡頭、事件、候選順序與正確候選／接回差異。R-4／R-6 的已有判定沿用 #589。
4. 以新 runner 驗證 E8 的 28/28 精確 G1，保留原版 notebook 的可重跑路徑；以校正 A4／B4／8CAM 的 8785 gate 收據決定共用 src 能否直接採用。若候選改變已承諾的既有回應位元組或決策，先回 Claude 與協調者審視世代遷移，再做任何 pin 更新。

## 本輪唯讀投影探針

從 #785 修訂版擷取實際 `ground_ieee` 的 AST，使用八台 R004 安全標定、兩種解析度及每台 41×31 個網格腳點，逐點以 IEEE binary64 bytes（含有效／缺值標記）雜湊。共 **20,336** 點，**4,428** 缺值。Mac CPython 3.12.12 的現行 NumPy 與 D421 算術在此取樣的位元差為 0，最大差為 0。macOS 系統 CPython 3.9.6 的原生 arm64 與 Rosetta x86_64，用 list-backed 矩陣視圖只執行同一個固定純量函式，三組共用輸出 SHA-256 `59ec335fd11132b239ecae2b88f5d101fbaf866834d967dea40bdd807f45570c`。這個覆蓋限於校正網格與 Rosetta 的算術，native Linux、Colab 正式 gate 與完整 replay 留待核准後驗證。

獨立合成邊界檢查另覆蓋 2,011 筆（2,005 有效），含 horizon、`t=0`、`t=80` 與相鄰值。在這組中，舊 Mac projector 與先轉 binary64 的候選位元差 0；候選的 arm64／Rosetta 位元輸出也相同（SHA-256 `b649eef49fc04de385f0c3a456010c68c84e75cc69cbd747b91f45d6635f4ff3`）。合成輸入與真實標定網格是兩組不同證據。

- LOCAL 標定 `local/data/live-assets-20261115/cameras.catalog.json`（12,793 bytes／1，SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`），只讀凍結來源。
- Notebook 34,482 bytes／1，SHA-256 `6fa0b5530b1ad355ed8181d154fdc27bf4c1045a55dec1e5c24e40e2e0b5a05e`，依下列 exact-commit 命令取得。
- AC7 LOCAL manifests 與重建方式見 [#773 診斷](../operations/AC7_B05_TRACK_HASH_20261127.md)。本輪只讀小型 JSON，未另產生錄製。以下探針的文字輸出可重建。

在獨立 clone，`DATA` 指向唯讀 LOCAL data 根，`PYTHON` 指向原生已安裝 NumPy 的 Python，`SCRATCH` 指向工作目錄。

```sh
gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/Polalalabear/amidst/contents/notebooks/e8_colab_eval.ipynb?ref=f6f70f7cb361da6009893a5f40af0e1ddadf2649' \
  > "$SCRATCH/e8-notebook.json"
cat > "$SCRATCH/projection-probe.py" <<'PY'
import ast
import hashlib
import json
import platform
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

notebook, catalog, mode = sys.argv[1:]
cells = json.loads(Path(notebook).read_text())["cells"]
cell = next("".join(c["source"]) for c in cells if "".join(c["source"]).startswith("# === CELL 8:"))
fn = next(n for n in ast.parse(cell).body if isinstance(n, ast.FunctionDef) and n.name == "ground_ieee")
ns = {}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "e8_colab_eval.ipynb", "exec"), ns)
ground_ieee = ns["ground_ieee"]

class Matrix:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        rows, col = key
        return SimpleNamespace(tolist=lambda: [row[col] for row in self.rows[rows]])

cameras = sorted(json.loads(Path(catalog).read_text())["cameras"], key=lambda c: c["camera_id"])
if mode == "native":
    from amidst.live_mode.tracker import Projector
    projector = Projector(cameras)
else:
    projector = SimpleNamespace(cams={
        c["camera_id"]: (Matrix(c["camera_to_world"]), c["fx"], c["fy"], c["cx"], c["cy"], c["width"], c["height"])
        for c in cameras
    })

def key(xy):
    return b"\0" if xy is None else b"\1" + struct.pack(">dd", *xy)

fixed = hashlib.sha256()
native = hashlib.sha256()
n = null = bit_diff = null_diff = 0
max_abs = 0.0
for c in cameras:
    cam = c["camera_id"]
    for width, height in ((320, 180), (1280, 720)):
        for i in range(41):
            for j in range(31):
                args = cam, i * width / 40, j * height / 30, width, height
                expected = ground_ieee(projector, *args)
                fixed.update(key(expected))
                n += 1
                null += expected is None
                if mode == "native":
                    old = projector.ground(*args)
                    native.update(key(old))
                    bit_diff += key(expected) != key(old)
                    null_diff += (expected is None) != (old is None)
                    if expected is not None and old is not None:
                        max_abs = max(max_abs, *(abs(a-b) for a, b in zip(expected, old)))
print(platform.machine(), platform.python_version(), mode, f"n={n} null={null}", f"fixed={fixed.hexdigest()}")
if mode == "native":
    print(f"native={native.hexdigest()} bit_diff={bit_diff} null_diff={null_diff} max_abs={max_abs:.17g}")
PY
CATALOG="$DATA/live-assets-20261115/cameras.catalog.json"
PYTHONPATH=src "$PYTHON" -B "$SCRATCH/projection-probe.py" "$SCRATCH/e8-notebook.json" "$CATALOG" native
/usr/bin/arch -arm64 /usr/bin/python3 -B "$SCRATCH/projection-probe.py" "$SCRATCH/e8-notebook.json" "$CATALOG" fixed
/usr/bin/arch -x86_64 /usr/bin/python3 -B "$SCRATCH/projection-probe.py" "$SCRATCH/e8-notebook.json" "$CATALOG" fixed
```
