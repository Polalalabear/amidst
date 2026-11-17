# 來源紀錄（Provenance record）與 CI

Issue：#486（驗收 checkpoint 之後，SHA 由工具處理，不再手寫）。本文件只描述工具用法，不代表任何驗收或授權。

## 1. 工具

`scripts/provenance_record.py` 輸出 schema `amidst.provenance-record.v1`（已登記於 `configs/architecture/schema_registry_v1.json`）。

| 區塊 | 內容 |
| --- | --- |
| `git` | HEAD SHA、分支、`dirty`（工作區有未提交變更時為 `true`，並在 `working_tree` 明寫 DIRTY）；讀不到 git 則為 `UNKNOWN` |
| `inputs` | `--input` 傳入的檔案或 manifest：位元組數、SHA-256（串流計算，大檔不吃記憶體）；目錄則逐檔 hash 並給 `tree_sha256` |
| `models` | `--model-file` 權重檔的 SHA-256；`--ollama-model NAME` 的 digest（只查本機 `127.0.0.1:11434`，讀不到填 `UNKNOWN`） |
| `environment` | OS、CPU、記憶體、GPU（能取得才填）、Python 與主要套件版本、Node 版本 |
| `run` | 指令（金鑰樣式會被遮蔽為 `[REDACTED]`）、`started_at_utc`、`finished_at_utc`、label |
| `script` | 本腳本自身的 SHA-256 |

## 2. 安全規則

- **不讀、不輸出環境變數**：只有上表的白名單欄位；金鑰、token 不可能被帶出。`--command` 內的 `KEY=…`、`--api-key …`、`sk-…` 之類字串會被遮蔽，但請仍不要把 secret 放在指令列。
- **GT 隔離**：路徑（含 symlink 解析後）的任一層若命名為 `gt_private`、`ground_truth`，或含 `gt`／`visibility`／`depth`／`trajectory` 詞，一律拒絕（exit 2，不輸出任何 JSON）。目錄輸入內若有這類檔案也整個拒絕。
- 不連外部服務；唯一網路存取是選用的本機 Ollama。
- 紀錄只證明「用了什麼」，不授予任何核准。

## 3. 用法

```bash
.venv/bin/python scripts/provenance_record.py \
  --input data/some_manifest.json \
  --model-file path/to/weights.bin \
  --ollama-model qwen3:latest \
  --command "python scripts/measure_q1q5_baseline.py --scene office" \
  --started-at 2026-11-09T08:00:00Z \
  --output provenance_<實驗名>.json
```

`--skip-gpu-probe` 可略過 GPU 查詢（macOS 的 `system_profiler` 較慢）。

## 4. 實驗紀錄與量測要怎麼附

1. **跑之前**確認工作區乾淨（`git status`）；`dirty: true` 的紀錄不能當成可重現證據，要在紀錄裡說明原因。
2. **跑完立刻**用跑實驗的同一個 checkout 產生 JSON，`--command` 填實際指令，`--started-at/--finished-at` 填實驗起訖。
3. JSON 放在實驗輸出旁（repo 內小檔可進 Git；大檔或本機資料放 artifacts 目錄，並在紀錄中標 `LOCAL`）。
4. 實驗紀錄附錄貼上：HEAD SHA、各輸入 SHA-256、模型 digest、環境摘要，並連到該 JSON；不要手寫這些值。Colab 一鍵匯出同樣呼叫本腳本。
5. 一個實驗若有多組輸入，重複 `--input`；結果以 `UNKNOWN` 標示讀不到的欄位，不要猜。

## 5. CI（`.github/workflows/ci.yml`）

每次 push（所有分支）與 pull_request 在 ubuntu-latest 執行，沒有 secret、不上傳資料：

| 步驟 | 指令 |
| --- | --- |
| 架構 guard | `scripts/check_architecture_guard.py --base <PR base SHA；push 用 46835218c600d99b8c973e52f62e8dd95e79ff15>` |
| 前端 | `AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs` |
| Python | `pytest tests/q1q5 tests/evaluation tests/operations` |
| 格式 | `git diff --check <base>...HEAD` |

Python 與 Node 版本取自 `.python-version`／`uv.lock` 與 `.node-version`。結果與 commit SHA 寫在 job summary。

**真實資料測試在 CI 上不跑，需在本機跑。** CI 沒有 `AMIDST_DEMO_HOME`，這類測試會自動 skip；CI 綠燈不等於驗收通過。
