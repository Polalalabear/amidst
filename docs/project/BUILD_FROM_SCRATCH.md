# 從頭建置與重現（BUILD_FROM_SCRATCH）

返回 [README](README.md)。架構見 [SYSTEM_ARCH.md](SYSTEM_ARCH.md)，規格見 [SPEC.md](SPEC.md)。

本文件寫「從 Blender 建檔到工作台啟動」的完整流程，目標是讓另一個人照著做就能重現。**每一步都只寫 repo 裡實際存在的腳本、設定與收據**；repo 裡找不到的步驟標 **UNKNOWN**，並寫出缺什麼。除非另外註明，repo 檔案都在 `mainline/q1q5`@`796cc17` 讀取。

## 0. 先講結論：目前能重現到哪裡

| 步驟 | 能否只靠 repo 重現 | 缺什麼 |
| --- | --- | --- |
| 環境（Python 套件） | 部分 | `pyproject.toml`／`uv.lock` 沒有 torch、torchvision、Pillow、PyYAML；版本只記在 `configs/q1q5/linked_baseline_environment.json` |
| r004 場景建檔（`.blend`） | **不能** | 父檔 r003 `.blend` 與 r004 建檔腳本（`build_static_v2.py` 等）都是 LOCAL，不在 repo |
| P1 工程場景（B-05 用） | 可以（腳本在 repo） | 腳本會自己建幾何；但 demo 用的 P1 v4 包是否就是這份設定產生的：**UNKNOWN** |
| 路線與事件時刻 | 可以（規劃 JSON 與凍結檔在 repo） | — |
| r004 渲染（A4-1／B4-1） | **不能** | producer `render_cx7.py` 在 LOCAL 的 `gt_private/`，不在 repo |
| safe bundle 檢查 | 可以（checker 在 repo） | 需要已渲染的 LOCAL run 目錄 |
| 兩層圖標記 | 部分 | 建圖腳本在 repo；需要 LOCAL 靜態 provenance（`r004-prereview-team-v2_20261024/provenance`） |
| 宣告時鐘 | 可以 | — |
| RT-DETR 偵測索引（r004） | **不能**（尚未產製） | #118 只有計畫；r004 adapter、production decoder、核定參數都 **UNKNOWN**／未完成 |
| 擴充 Office 場景（多間教室＋COCO 物件） | **不能**（尚未建） | D126-2 已指派 Codex，repo 裡沒有腳本或設定 |
| Windows 啟動工作台 | 未驗證 | 沒有 Windows 版一鍵啟動腳本；repo 內沒有任何 Windows 實測紀錄 |

## 1. 環境

### 1.1 版本

| 項目 | 版本 | 出處 |
| --- | --- | --- |
| Blender | 5.2.1 LTS（build `9e2066aef7ef`，2026-08-25），引擎 `BLENDER_EEVEE` | `docs/engineering/R004_EVENT_RUNS_RECEIPT.md`、`docs/engineering/R004_BUILD_RECEIPT.md` §2 |
| Python | `>=3.12`；基準環境實際 3.12.12 | `pyproject.toml`、`configs/q1q5/linked_baseline_environment.json` |
| 專案依賴 | matplotlib≥3.10、networkx≥3.7、numpy≥2.5.3、pydantic≥2.13.5、psycopg[binary]==3.3.6、rerun-sdk≥0.38.1、shapely≥2.1.2,<3；dev：pytest≥9.1.1、ruff、mypy | `pyproject.toml`、`uv.lock` |
| 偵測額外依賴 | torch 2.6.0、torchvision 0.21.0、Pillow 13.0.0、PyYAML 6.0.3 | `configs/q1q5/linked_baseline_environment.json`（`extra_existing_runtime_dependencies`） |
| RT-DETR | 官方 R18；source commit `df2a96c8c3a098567a1149bf0248da6efe6d495d`；source zip SHA-256 `e6014ae32d2d…6564`；權重 SHA-256 `3ba8b5c909c9…66f0`（81,001,853 bytes） | `linked_baseline_environment.json`；`R004_BUILD_RECEIPT.md` §3；`docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md` 外包 Windows 表 |
| Node | 前端測試與 event-viewer 需要；版本 **UNKNOWN**（repo 沒有記錄 demo 機的 Node 版本） | `docs/operations/DEMO_RUNBOOK_20261104.md` §1 第 3 項只要求 `node --version` 可用 |
| uv | 專案用 `uv run`；版本 **UNKNOWN**（`pyproject.toml` 的 build backend 要求 `uv_build>=0.9.26,<0.10.0`） | `pyproject.toml` |
| Ollama／Qwen | `qwen3:1.7b-q4_K_M`，只有 AGENT_SEQUENTIAL 需要；兩個核心的 demo 不需要 | `linked_baseline_environment.json` |

### 1.2 Windows 安裝

repo 裡**沒有** Windows 安裝腳本或實測紀錄。`Q1Q5_QWEN_CONTENTION_MIGRATION.md` 的「外包 Windows」一節明寫：目前未做 Windows 啟動／推論／瀏覽器驗證，不能只給 `git clone`＋`uv sync` 就稱可重現；不要搬 Mac 的 `.venv` 當 Windows 環境。依該節，安裝要分兩組：

| 用途 | 需要 |
| --- | --- |
| A. 只看錄製重播與 UI | Python 3.12＋專案依賴、Node、safe RGB；**不需要** Blender、RT 權重、Qwen |
| B. 重跑模型推論 | A 再加 torch 2.6.0／torchvision 0.21.0／Pillow／PyYAML、RT-DETR 官方 source 與權重（核對上表 SHA） |
| C. 從頭渲染 | B 再加 Blender 5.2.1 LTS |

建議步驟（一般工具的安裝方式，**未在 Windows 驗證**）：

1. 安裝 Python 3.12、uv、Node、Git for Windows；C 組另裝 Blender 5.2.1 LTS（blender.org 官方版）。
2. 在 repo 根目錄 `uv sync` 建立專案本地環境（依 `uv.lock`）。
3. B 組另外在同一個環境裝 torch 2.6.0、torchvision 0.21.0、Pillow 13.0.0、PyYAML 6.0.3。CPU 或 CUDA 版本的選擇：**UNKNOWN**（基準機是 arm64 CPU）。
4. 依外包 Windows 表填環境清單：Windows 版本／原生或 WSL2、CPU、RAM、GPU／VRAM、磁碟可用量；查不到的填 UNKNOWN。
5. 跨平台環境自檢 `python scripts/ensure_env.py [--repo <路徑>] [--min-free-gib 8] [--json]`（D116-2；預設要求可用磁碟 ≥ 8 GiB，D118）。
6. 乾淨 clone 驗證 `python scripts/verify_clean_clone.py [--repo <路徑>] [--base origin/mainline/q1q5] [--quick] [--skip-tests] [--json]`：跑環境檢查、架構守門與測試；`--json` 輸出結構化收據。
7. Windows 一鍵啟動 `start_all_demo.ps1`（參數：`-P1Bundle`、`-CX7Root`、`-StateParent`、`-Python`、`-PortRec` 8766、`-PortLive` 8765、`-PortCx` 8780、`-NoOpen`、`-CheckOnly`）。以上三支腳本已在 repo，但在 Windows 實機的完整結果 **待補**（本文件未重跑）。

### 1.3 路徑寫法

本文件的 LOCAL 位置一律用 pathlib 寫，Windows 和 macOS 都適用：

```python
from pathlib import Path
import os

REPO = Path.cwd()                                    # repo 根目錄
ARTIFACTS = Path(os.environ.get("AMIDST_ARTIFACTS", Path.home() / "amidst-artifacts"))
CX7_ROOT = ARTIFACTS / "r004-cx7-d115-20261102-01a199f8"   # 既有 CX-7 輸出
A4_SAFE = CX7_ROOT / "A4-1" / "safe" / "media"            # 只讀這裡
A4_PRIVATE = CX7_ROOT / "A4-1" / "gt_private"             # 不讀、不列、不複製
STATE_PARENT = Path.home() / "amidst-demo-state"
```

`AMIDST_ARTIFACTS` 未設時預設 `Path.home() / "amidst-artifacts"`，這是建圖腳本的慣例（`docs/engineering/R004_GRAPH_RECEIPT.md`「驗證與重現」）。repo 內的現有腳本大多用 `Path(__file__).resolve().parents[1]` 找 repo 根目錄（例如 `scripts/start_q1q5_p1.py` 第 10、28 行）。

## 2. 建檔

### 2.1 r004 場景（A4-1、B4-1 用）

**來源鏈**（`docs/engineering/R004_BUILD_RECEIPT.md` §1）：

| 產物 | 位置（相對 `ARTIFACTS`，r003 除外） | SHA-256 |
| --- | --- | --- |
| r003 父檔 | `REPO / "data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend"`（**不在 git 裡**，`git ls-files data/pilot` 為空） | `6e7de38d…ae6d8e` |
| r004 v2（現用） | `ARTIFACTS / "r004-build-v2-20261021" / "controlled_scene_v1_s001_r004.blend"` | `466e6fbe…3809b` |
| 靜態相機 catalog（8 台） | `ARTIFACTS / "r004-build-v2-20261021" / "safe_static" / "cameras.json"` | `3eba8572…b899f` |
| 靜態幾何提案 | 同目錄 `safe_static/static_geometry.PROPOSED.json` | `bed91c8b…f988a` |

**建檔腳本**：`build_preview.py`、`build_static_v2.py`、`render_previews.py`、`measure_preview.py` 都是 **LOCAL**（收據 §4：「產製腳本與 private preview poses 留在 LOCAL」），repo 裡沒有。所以**從零建出 r004 `.blend` 的步驟是 UNKNOWN**。缺：r003 `.blend` 本身、r003 的建檔方式、r004 v2 建檔腳本。

**場景設計**（`docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` §2，D68 核定）：在 r003 上新增西側入口、室外地面、靜態車輛、8 台鏡頭與中性牆地材質。實際尺寸與座標要讀 LOCAL 的靜態幾何。

**區域命名**（`configs/q1q5/graphs/r004/region_graph_v3_1.json`）：

| 區域 ID | 意思（#397 §E.3.1） |
| --- | --- |
| OUT_W | 室外 |
| VEST_W | 門廳 |
| CORR_W | 走廊 |
| CORNER | 轉角 |
| CORR_N | 北走廊 |
| R101、R102 | 房間 |

通道：E_OUT_VEST、E_VEST_CORR、E_W_CORNER、E_CORNER_N、E_PORTAL_R101、E_PORTAL_R102，全部 `TOPOLOGICAL_ONLY`、`state=UNKNOWN`。

**攝影機**（`R004_BUILD_RECEIPT.md` §2）：8 台 pinhole、960×540、square pixels、sensor fit HORIZONTAL、lens shift 0、主點 (480, 270)；`camera_to_world` 用 `BLENDER_NEG_Z_UP_Y`，像素 `TOP_LEFT_CONTINUOUS`。

| 鏡頭 | fx＝fy（px） | 由 fx 推得的水平視角 |
| --- | ---: | ---: |
| CAM_BRANCH、CAM_ENTRY、CAM_W1、CAM_W2 | 625.548197 | 75° |
| CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_R101_IN | 685.511068 | 70° |
| CAM_WIDE | 480.000000 | 90°（使用者選定，見收據 §2） |

視角是用 `2·atan(480 / fx)` 算的，和提案表的 70°／75°／90° 一致。**鏡頭的世界座標、朝向、焦距（mm）與 sensor 寬度：UNKNOWN**，只存在 LOCAL 的 `cameras.json`（SHA `3eba8572…`），repo 只有各台的 `calibration_sha256`。

**人物模型與動畫**（`R004_EVENT_RUNS_RECEIPT.md`「來源與凍結綁定」）：沿用來源 `.blend` 既有的紅衣 P1 模型、材質和 frame-1 姿勢，**只在記憶體依凍結控制點線性平移，沒有步態動畫**。D124 已授權重渲染改成「轉彎時會轉身、看得出正反面」，做法與產物：**UNKNOWN**（尚未交付）。

**物件擺放**：r004 有室外靜態車輛（提案 §2）。COCO 物件的擺放清單：**UNKNOWN**；`docs/evaluation/R004_STATIC_QUESTIONABLE_OBJECTS_20261029.md` 有靜態物件的疑義清單，可當參考。

### 2.2 P1 工程場景（B-05a／B-05b 用）

`scripts/render_q1q5_dynamic_rgb.py` 是 repo 裡唯一會**自己建幾何**的 Blender 腳本（docstring：「Never loads an existing asset」），讀 `configs/q1q5/dynamic_engineering_v1.json`：

| 欄位 | 值 |
| --- | --- |
| scene_id／run_id | `ENGINEERING_DYNAMIC_SCENE`／`ENGINEERING_DYNAMIC_RUN_20261025` |
| 長度、fps、解析度、取樣 | 8 s、20 fps、960×540、16 samples、seed 7 |
| 鏡頭 A | position (2, −5.5, 2.8)，look_at (4, 0, 1)，45 mm |
| 鏡頭 B | position (16, −5.5, 2.8)，look_at (14, 0, 1)，45 mm |
| 人物動作（private） | x 從 1.5 走到 16.5，y＝0，步頻 1.6 Hz |
| 限制 | `PRODUCER_ONLY`、`NO_GT_IN_INFERENCE`、`NO_FORMAL_ACCEPTANCE`、`IDENTITY_UNCONFIRMED` |

demo 實際用的是 LOCAL 的 P1 v4 包（MANIFEST `6e9a0a4c…f1d7`，A、B 各 160 張、20 fps、8 s；[D113](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6575688787)）。**P1 v4 包是否就是用這份設定產生：UNKNOWN**；#397 §E.2.1 也記錄 P1 的 Blender 場景檔與盲區位置為 UNKNOWN。

### 2.3 擴充 Office 場景（D126-2）

多間標註教室（例如 R101～R104）各有室內鏡頭、放 COCO 物件：**UNKNOWN，尚未建**。repo 沒有建檔腳本、場景設定或命名表。要補：建檔腳本、每間教室的區域 ID 與通道、室內鏡頭的 catalog、COCO 物件清單（類別必須在 `configs/q1q5/class_alias_v1.json` 的 80 類內）。

## 3. 路線與事件

路線不是寫在 Blender 裡，而是先寫成「不可執行的規劃 JSON」，再凍結：

| 檔案 | 內容 |
| --- | --- |
| `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` | 情境卡：每段時間、區域、預期鏡頭、走位、計分事件 |
| `configs/q1q5/scripts/r004_a4_1_script_draft_v1.json`、`r004_b4_1_script_draft_v1.json` | producer 規劃：`planning_waypoints`（時間 µs＋腳點世界座標 m）、`planning_legs`（段長、速度）、`planning_cues`（離開／到達提示） |
| `configs/evaluation/r004_a4_1_script_plan_v1.json`、`r004_b4_1_script_plan_v1.json` | 評分計畫 |
| `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json`／`.md` | 凍結候選：13 個來源 pin、事件表、D79 窗；凍結 SHA `ab45a832…63fb`（#354@`48133c1`，D105-1） |

凍結檔的事件時刻（秒，從 run 起點算）：

| 場次 | 事件 | 預期動作 | t_X | t_N | 計分 |
| --- | --- | --- | ---: | ---: | --- |
| A4-1 | A4-c1 | SWITCH | 8 | 11.0 | 是 |
| A4-1 | A4-n1 | NO_SWITCH | 16 | — | 是 |
| A4-1 | A4-e | SWITCH | 26 | 29.0 | 否 |
| A4-1 | A4-c2 | SWITCH | 36 | 39.0 | 否 |
| B4-1 | B4-n1 | NO_SWITCH | 4 | — | 是 |
| B4-1 | B4-b | SWITCH | 11 | 14.0 | 是 |
| B4-1 | B4-d | SWITCH | 21 | 24.0 | 否 |
| B4-1 | B4-e | SWITCH | 30 | 32.0 | 否 |

A4-1 長 50 s、查詢 [0, 48) s；B4-1 長 42 s、查詢 [0, 40) s；5 fps，取樣間隔 200,000 µs。逐段路線見 #397 §E.3.2。

**B-05**：P1 沒有凍結劇本（#397 §E.2.1）；人物動作只有 `dynamic_engineering_v1.json` 的 `private_motion`。B-05a／B-05b 的時點（2.50 s 暫失、5.15 s 切到 B）是**系統輸出**，不是劇本設計值（D113）。

規劃 JSON 的 `must_not_enter` 明列：不得進入推論、候選排序、偵測索引、參數、prompt、safe bundle。

## 4. 渲染

### 4.1 r004（A4-1、B4-1）

| 項目 | 值 | 出處 |
| --- | --- | --- |
| producer | LOCAL `gt_private/render_cx7.py`（SHA `60ca8170…687b`），**不在 repo** | `R004_EVENT_RUNS_RECEIPT.md` |
| 引擎、取樣 | BLENDER_EEVEE，16 samples（來源 64，為加速只調取樣） | 同上 |
| fps、解析度、格式 | 5 fps、960×540、RGB PNG | 同上 |
| 張數 | A4-1 4 台×250＝1000；B4-1 5 台×210＝1050 | 同上 |
| run_id | `ctrl-lcorr-s1-a4-5fps-v1-r004`、`ctrl-lcorr-s1-b4-5fps-v1-r004` | 同上 |

渲染指令：**UNKNOWN**（producer 不在 repo）。缺：`render_cx7.py` 本身與它的參數。

**輸出目錄**（相對 `CX7_ROOT`）：

```text
A4-1/
  safe/media/<camera_id>/<index>.png    ← 去除 metadata 的 RGB，唯一可給推論端
  gt_private/                           ← 原始 PNG、LOCK、frame journal（含路線）、completion、hash
B4-1/
  （同上）
```

**磁碟估算**（`R004_EVENT_RUNS_RECEIPT.md`「已產生的 run」表）：

| run | raw PNG（gt_private） | safe RGB | 合計 |
| --- | ---: | ---: | ---: |
| A4-1 | 538,357,066 bytes | 538,013,316 bytes | 1,076,370,382 bytes |
| B4-1 | 566,772,435 bytes | 566,413,125 bytes | 1,133,185,560 bytes |
| 兩段合計 | 1,105,129,501 bytes | 1,104,426,441 bytes | 2,209,555,942 bytes（約 2.06 GiB） |

平均約 0.54 MB／張，raw 與 safe 各一份。另外依 [D118](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6580320736)，**可用磁碟低於 8 GiB 就要停止渲染**，所以開始前至少要有 8 GiB＋本次輸出量。

### 4.2 P1 工程場景

腳本 docstring 給的指令（`scripts/render_q1q5_dynamic_rgb.py` 第 3–4 行）：

```text
blender --background --factory-startup --disable-autoexec --python scripts/render_q1q5_dynamic_rgb.py -- --config <絕對路徑>/configs/q1q5/dynamic_engineering_v1.json --output <不存在的新絕對路徑> [--pilot]
```

- `--output` 必須是**不存在**的新目錄（第 85 行 `assert ... not out.exists()`）。
- 輸出：`private_producer/`（權限 0o700）與 `safe/media/`；只有 `safe/rgb.json`、PNG 與 `static.json` 可給推論端（docstring）。
- Windows 上 `blender` 要換成 Blender 安裝路徑的 `blender.exe`；**未在 Windows 驗證**。

### 4.3 safe bundle 怎麼產生

1. producer 渲染時就把 raw 放 `gt_private/`、去除 tEXt／iTXt／zTXt／eXIf 的 RGB 放 `safe/media/`（收據「LOCAL 證據與隔離」）。
2. D119 的工程機械投影：把 safe 區組成只含 `manifest.json`、兩份 run descriptor、原 bytes 的 clock／catalog 與 2050 張 RGB 的 bundle。執行的 helper 是 LOCAL（`/private/tmp/amidst-cx7-wire-01a19f68-project.py`），**不在 repo**；所以投影步驟本身 **UNKNOWN**。
3. 用 repo 的 checker 驗證（見 [§6](#6-驗證每一步做完怎麼檢查)）。

## 5. 標記

### 5.1 region_graph 與 camera_graph

**怎麼標**（`docs/engineering/R004_GRAPH_RECEIPT.md`）：

- 只用 safe 靜態幾何、calibration、membership 與**無人物的靜態畫面**；不讀事件、GT、renderer visibility／depth。
- **covered_regions**：人工在靜態畫面上判定某台鏡頭看得到哪些區域，`basis=MANUAL_ON_STATIC_FRAME`，`visibility_ref` 形如 `static-review:v3:<camera>:<region>`，`visible_area_m2=null`。
- **entry／exit zones**：每台鏡頭在畫面上畫 ROI 多邊形（`roi_polygon_px`），ID 為 `CAM_*:ENTRY_V3:<通道>` 或 `CAM_*:EXIT_V3:<通道>`；每塊 ROI 以九個足點做靜態見證。v3 共 26 塊 ROI（12 入口＋14 出口）。D71 要求每台鏡頭都有出口。
- **transitions**：56 個有向鏡頭對全部列出，22 條轉移、34 條附理由排除；每條轉移記 `via_exit_zone_ids`、`to_entry_zone_ids`、`edge_path`、`region_path`；`relation=UNKNOWN`、`ranking_area_m2=null`。D77 排除 BRANCH↔WIDE、EXT_CAR↔EXT_CLEAR。
- CAM_ENTRY 依 D74 只供查找，不在追蹤圖裡（查找 8 台、追蹤 7 台）。

**建圖指令**（收據「版本、pin 與重現」）：

```text
uv run python scripts/build_r004_review_v2.py --graph-v3-1 \
  --config configs/q1q5/graphs/r004/build_plan_v3_1.json \
  --config-sha256 <sidecar 裡的 SHA> \
  --base-graphs configs/q1q5/graphs/r004 \
  --static-provenance <ARTIFACTS / "r004-prereview-team-v2_20261024" / "provenance"> \
  --output <新目錄>
```

缺：`--static-provenance` 指向的 LOCAL 靜態 provenance（`source_static_geometry`、`static_membership`、`region_meshes`、`camera_catalog` 四份）不在 repo。圖要經 Claude 獨立檢查、使用者核准（G4）；目前 v3_1 兩張圖都是 `DRAFT`。

### 5.2 宣告時鐘

每個 run 寫一份 `configs/q1q5/clocks/<run>.json`（schema `q-demo.clock-mapping.v1`；規則見 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` §3.1）：

| 欄位 | A4-1 的值 |
| --- | --- |
| `mapping_kind` | `DECLARED_DEMO_CLOCK` |
| `timezone` | `Asia/Taipei` |
| `wall_origin` | `2026-11-01T14:00:00+08:00`（B4-1 為 14:10） |
| `t0_us`、`rate` | 0、1 |
| `source_duration_us` | 50000000（B4-1 為 42000000） |
| `declaration_source`、`declared_by`、`declared_at` | 誰在哪裡宣告（#93 留言連結） |
| `content_sha256` | 內容 hash |

規則：`wall_origin` 的 UTC 偏移要和 `timezone` 一致；不得依事件答案回推時鐘；改了對應，所有下游 hash 都會變。驗證方式見 `docs/engineering/R004_RUN_CLOCK_DECLARATIONS_20261026.md`「重現驗證」：用 `ClockMapping.from_document` 讀入，再以 `resolve_source_range` 驗完整範圍與查詢範圍為 READY。

### 5.3 RT-DETR 偵測索引

- 產生器：`scripts/build_q1q5_detection_index.py`，參數 `--repo --config --config-sha256 --run-id --weights --model-source --output`，另要 `--permit-real-rgb` 明示授權；參數集必須是 `APPROVED`，且要有 `index_score_floor`、`stride_samples`、`index_grid_origin_frame`、`hsv_config`。
- 模型：`src/amidst/q1q5/detection_index.py` 的 `OfficialRTDetrR18`，80 類、strict load、不下載、不另做 NMS。基準設定 CPU、2 threads、seed 7、輸入 640×640（`R004_BUILD_RECEIPT.md` §3；`docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`）。
- **r004 現況：不能直接跑**。`docs/engineering/R004_INDEX_RECEIPT.md`（#118，PLAN／NOT_RUN）寫明：產生器目前只接受 A/B1 registration 並硬寫 `scene_revision="r003"`；`configs/q1q5/parameter_set_v1.json` 仍 `PROPOSED`、score floor 為 null；production decoder 與正式 producer 指令 **UNKNOWN**。缺：r004 safe-only adapter、核定參數集、production receipt decoder。

### 5.4 GT 與 `gt_private/` 隔離（流程）

1. 渲染時分兩個資料夾：`safe/`（可給推論）與 `gt_private/`（原始 PNG、路線 journal、LOCK、完整性報告）。
2. 規劃 JSON、凍結劇本、情境卡、評分計畫都不進 safe bundle；checker 看到任何劇本檔名或 hash 出現在 manifest 就 FAIL（`R004_A4B4_SCRIPT_FREEZE_20261029.md`「Safe bundle」）。
3. safe PNG 去除文字與 EXIF 區塊；event-viewer 啟動時再逐張驗 PNG 結構，`gt_private/` 一律 404（`frontend/event-viewer/README.md`）。
4. 推論端（索引、Q1、Q2、Agent）只讀 safe 區與凍結的圖、時鐘、參數。
5. 評分端另外讀 hash-pinned 劇本，和決策分開（`docs/specs/Q1Q5_PRODUCT_SPEC.md` §2）。
6. 架構守門檢查程式碼沒有越界讀取（[§6](#6-驗證每一步做完怎麼檢查)）。
7. 操作時**不要列出、開啟或複製** `gt_private/`（運行手冊 §1 第 2 項）。

## 6. 驗證：每一步做完怎麼檢查

指令照 repo 原文；`AMIDST_REQUIRE_IMPL=1` 讓測試在實作缺席時失敗而不是 skip。Windows 上設環境變數的寫法不同（PowerShell：`$env:AMIDST_REQUIRE_IMPL=1`），**未在 Windows 驗證**。

| 步驟 | 指令 | 預期結果 | 出處 |
| --- | --- | --- | --- |
| 劇本凍結 | `uv run python scripts/check_r004_script_freeze.py --freeze docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json --expected-freeze-sha256 ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` | exit 0，candidate consistency PASS，13 個參照 bytes 不變 | `R004_EVENT_RUNS_RECEIPT.md` 實際產出 |
| 劇本測試 | `AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_r004_script_freeze.py tests/unit/test_q5_script_adapter.py` | 全過 | `R004_A4B4_SCRIPT_FREEZE_20261029.md` |
| 兩層圖 | `uv run python -m pytest tests/unit/test_r004_review_v2.py -q` | 33 PASS（v3_1） | `R004_GRAPH_RECEIPT.md` |
| 圖靜態預審 | `python scripts/check_q1q5_graphs.py --config <inputs.json> --config-sha256 <SHA> --output <新路徑>` | 產出 GRAPH_CHECK 報告；不授予核准 | `docs/engineering/R004_GRAPH_CHECK.md`「重現」 |
| 宣告時鐘 | `ClockMapping.from_document`＋`resolve_source_range` | 完整範圍與查詢範圍皆 READY、coverage_complete | `R004_RUN_CLOCK_DECLARATIONS_20261026.md` |
| safe bundle | `uv run python scripts/check_event_run_bundle.py --profile r004-a4b4 --bundle <LOCAL bundle> --receipt <LOCAL receipt.json>` | exit 0；A4-1 1000 張、B4-1 1050 張 PASS（ENGINEERING／D119） | `R004_EVENT_RUNS_RECEIPT.md` |
| safe bundle 測試 | `AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_event_run_bundle.py` | 176 passed（2026-11-03 紀錄） | 同上 |
| 偵測索引 | `tests/q1q5/test_detection_index.py`、`test_hsv_color.py`、`test_check_detection_index_receipt.py` | r004 正式驗證 **UNKNOWN**（#118 未產製） | `R004_INDEX_RECEIPT.md` |
| 物理預測 | `uv run python -m pytest -q tests/q1q5/test_physical_prediction.py` | 全過（本文件未執行） | 檔案存在於 repo |
| 架構守門 | `python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5`（**不帶** `--allow`） | authority／inference／schemas 全 PASS、0 findings | #408 實際產出 |
| 前端 | `node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs` | 0 fail（#408 時 410 pass） | #408 實際產出 |
| 文件 | `git diff --check` | 無輸出 | `AGENTS.md` |

已知不是全綠：`tests/evaluation/test_p2_baseline_report.py` 在 mainline 基底有 8 項既有失敗（`R004_EVENT_RUNS_RECEIPT.md`「mainline PR 交件重驗」）。

## 7. 在 Windows 上跑起工作台

`start_all_demo.command`（[#408](https://github.com/Polalalabear/amidst/pull/408)，OPEN）是 Bash 腳本，用 `set -m`、process group、`lsof` 類的檢查，只能在 macOS 用。`Q1Q5_QWEN_CONTENTION_MIGRATION.md` 也列出舊啟動器依賴 `fcntl`、Homebrew、`lsof`、`df`。**repo 裡沒有 Windows 版啟動腳本，下面的替代步驟沒有任何 Windows 實測。**

替代做法：照運行手冊 §2～§4 的原指令，分三個終端機（PowerShell）各啟動一段，自己準備路徑與 state 目錄。

**準備**

```python
# 在 Python 裡先確認路徑（pathlib 寫法）
from pathlib import Path
P1_BUNDLE = Path(r"<P1 v4 包的位置>")          # 需含 MANIFEST.json，SHA-256 6e9a0a4c…f1d7
CX7_ROOT = Path.home() / "amidst-artifacts" / "r004-cx7-d115-20261102-01a199f8"
STATE_PARENT = Path.home() / "amidst-demo-state"
STATE_PARENT.mkdir(parents=True, exist_ok=True)
# 每次啟動都用一個「不存在」的新子目錄當 --state-root，例如 STATE_PARENT / "rec-<時間>"
```

P1 v4 包與 CX-7 safe RGB 都是 LOCAL，要另外取得；repo 不含。

**段 A：錄製伺服器（埠 8766）**，手冊 §2 A1：

```text
python -S scripts/start_q1q5_p1.py --bundle <P1_BUNDLE> --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root <STATE_PARENT/rec-新目錄> --current-ui --no-open --port 8766
```

**段 B：live 追蹤（埠 8765）**，手冊 §3：

```text
python -S scripts/start_q1q5_p1.py --bundle <P1_BUNDLE> --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root <STATE_PARENT/live-新目錄> --tracking-scope <REPO/configs/q1q5/p1_live_tracking_scope.json> --tracking-scope-sha256 e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8 --current-ui --no-open --port 8765
```

**段 C：複雜事件播放（埠 8780）**，手冊 §4／`frontend/event-viewer/README.md`：

```text
node frontend/event-viewer/server.mjs --root <CX7_ROOT> --port 8780
```

**開瀏覽器**：`http://127.0.0.1:8766/workbench-v2/`（監控牆）、`http://127.0.0.1:8766/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938`（B-05b）、`http://127.0.0.1:8765/workbench-v2/`（B-05a）、`http://127.0.0.1:8780/`（複雜事件）。事件選單把三段整合在同一頁，要等 #408 合併。

**Windows 上可能的差異（未驗證）**

| 項目 | 說明 |
| --- | --- |
| 磁碟檢查 | 手冊用 `df -g /`；Windows 改跑 `python scripts/ensure_env.py`（預設 ≥ 8 GiB，D118）；手冊要求 ≥ 9 GiB 才啟動（手冊 §1 第 1 項）。`start_all_demo.ps1` 自己只擋 < 1 GiB（只啟動 UI；渲染或產製仍以 ≥ 8 GiB 為準），`-CheckOnly` 只做檢查不啟動 |
| 埠檢查 | 手冊用 `lsof`；Windows 用 `netstat -ano` 看 8765／8766／8780 有沒有被占 |
| 關閉 | 每個終端機各自 Ctrl-C；沒有一鍵全部關閉 |
| 路徑 | 含空白的路徑要加引號；`--state-root` 必須是不存在的新路徑 |
| `start_q1q5_p1.py` | 用 `Path(__file__).resolve()` 找 repo，理論上跨平台；但有沒有呼叫 macOS 專屬命令：**UNKNOWN**（未逐行審查） |
| event-viewer 路徑守門 | 逐段 `lstat`、拒絕 symlink；在 NTFS（含 junction）上的行為：**UNKNOWN** |

## 8. UNKNOWN 與要補的東西

| # | 缺什麼 | 影響的步驟 |
| --- | --- | --- |
| 1 | r003 `.blend`、r004 v2 建檔腳本（`build_static_v2.py` 等） | §2.1 建檔 |
| 2 | 鏡頭世界座標、朝向、焦距（mm）、sensor 寬度（LOCAL `cameras.json`） | §2.1 |
| 3 | P1 v4 包與 `dynamic_engineering_v1.json` 的對應 | §2.2 |
| 4 | 擴充 Office 場景的建檔腳本、區域、鏡頭、COCO 物件清單 | §2.3 |
| 5 | D124 重渲染（轉身、正反面）的做法 | §2.1、§4.1 |
| 6 | r004 producer `render_cx7.py` 與渲染指令 | §4.1 |
| 7 | D119 safe bundle 投影 helper | §4.3 |
| 8 | 建圖用的 LOCAL 靜態 provenance | §5.1 |
| 9 | r004 索引 adapter、核定參數集、production decoder | §5.3 |
| 10 | `scripts/ensure_env.py`、`scripts/verify_clean_clone.py`、`start_all_demo.ps1` 已存在；缺 Windows 實機執行結果 | §1.2、§7 |
| 11 | Node、uv 的版本；torch CPU／CUDA 選擇 | §1.1 |
