# 影像裁決測試：Colab 本機視覺模型測試包（2026-11-16）

- Model / effort：Fable 5.2；effort 沒有記錄（這個 session 看不到自己的 effort 設定）。
- 設計：PR [#547](https://github.com/Polalalabear/amidst/pull/547) 的 `docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0D。OpenAI 那一邊的結果：[`LIVE_MODE_ADJUDICATION_20261116.md`](../evaluation/LIVE_MODE_ADJUDICATION_20261116.md)。
- **不需要 API key，不呼叫 OpenAI，不花錢。** 包裡沒有標準答案；正確率回到 Mac 上評分。
- **2026-11-16 更新：使用者已經在 Colab L4 上跑完這個包。** 兩個 Qwen 視覺模型正常跑完；`llama3.2-vision` 在 Ollama 0.40.16 上載入失敗（`unknown model architecture: 'mllama'`），沒有結果。結果和硬體規格在 [`LIVE_MODE_ADJUDICATION_20261116.md`](../evaluation/LIVE_MODE_ADJUDICATION_20261116.md) §3.2。下面「沒驗證的部分」是出包當時的狀態。
- 下一次要再跑：把 `llama3.2-vision` 換成 `gemma3:12b-it-q4_K_M`（標籤確認存在，沒有跑過）。

## 工作內容

在 Colab 的 GPU 上用 Ollama 跑看得懂圖的開源模型，回答 36 題「畫面裡哪個編號的人是目標」。題目和 OpenAI 那一邊相同，來自即時模式實際出現的裁決時刻。每題跑兩次：看圖，以及只看從畫面量出來的數字（對照組）。

現有 Colab 上的 `qwen2.5:7b-instruct` 和 `llama3.1:8b-instruct` 是純文字模型，看不了圖，所以要換模型。

## 建議的模型

三個都是 q4_K_M，標籤在 2026-11-16 從 Ollama 的模型庫頁面確認存在：

| 模型 | 為什麼選 | 大小（概略） |
| --- | --- | --- |
| `qwen2.5vl:7b-q4_K_M` | 和現有的文字模型 Qwen 2.5 7B 同一家族、同一個大小，最好比較。**首選** | 約 6 GB |
| `qwen3-vl:8b-instruct-q4_K_M` | Qwen 系列比較新的一代，看同樣大小下新一代差多少 | 約 6 GB |
| `llama3.2-vision:11b-instruct-q4_K_M` | 和現有的 llama3.1 8B 同一家族，當作不同家族的對照 | 約 8 GB |

模型大小是概略值，沒有實際下載確認。三個模型在這種題目上的表現都沒有量過，「首選」只是因為最容易和現有結果比較。

據我所知 `llama3.2-vision` 一次只接受一張圖（沒有實測）。為了讓三個模型的輸入一致，包裡每一題是一張合成圖：左邊是參考圖，右邊是標了編號的鏡頭畫面。OpenAI 那一邊是兩張圖分開送，這是兩邊的一個差別。

## GPU 規格

建議 **L4（24 GB）**，和文字模型的比較（D175）一致，三個模型都放得下。沒有 L4 時 T4（16 GB）應該也放得下，但延遲不能和 L4 的結果直接比；報告會自動標出來。沒有 GPU 時腳本會拒絕執行。建議開高 RAM。

## 產物（LOCAL，不進 Git）

資料夾 `local/data/adjudication-colab-pack-20261116/`：

| 路徑 | 大小（bytes） | 檔案數 | SHA-256 |
| --- | ---: | ---: | --- |
| `adjudication-pack_colab_20261116.zip`（**上傳這個**） | 1,666,321 | 43（zip 內） | `9976bd4cbdd336fc250e6b7d24b73e12f265ddaa94e917fd63befece0a793b55` |
| `adjudication_vision_colab.ipynb`（**在 Colab 開這個**；和 zip 內的相同） | 8,644 | 1 | `46f7c48f2823440c196885e1fbf04da010612ebdd76d911b26eb935ef87472ec` |
| `adjudication-pack_colab_20261116/`（解開的資料夾） | 約 1.9 MB | 43 | `MANIFEST.json`：`fadeb69abd4c5eb7b2312a62906e1a799a0cc2382b827288973880e41830521e` |

包的內容：`data/questions.jsonl`（36 題，沒有角色代號和劇本位置）、`data/img/` 36 張合成圖、`run_vision_probe.py`、`adjudication_vision_colab.ipynb`、`tools/verify_pack.py`、`README.md`、`MANIFEST.json`、`RETURN/README.txt`。

重新產生（需要 Pillow；輸入是 LOCAL `local/evidence/live-mode-adjudication-20261116/questions/`，SHA-256 在設計稿 §0D）：

```bash
python scripts/live_mode/build_adjudication_colab_pack.py --questions local/evidence/live-mode-adjudication-20261116/questions --out local/data/adjudication-colab-pack-20261116
```

zip 用固定的時間戳和排序，同樣的輸入會得到同樣的 SHA-256。

## 操作步驟（使用者在 Colab 做）

1. 在 Colab 上傳並開啟 `adjudication_vision_colab.ipynb`。
2. 執行階段 → 變更執行階段類型 → L4 GPU，建議開高 RAM。
3. 從上到下依序執行。步驟 0 會跳出選檔視窗，選 `adjudication-pack_colab_20261116.zip`。
4. 步驟 4 最久：下載三個模型，加上 216 次推論。預估 30–50 分鐘，這是推估，沒有實測。
5. 步驟 5 顯示硬體規格和結果。步驟 6 下載 `adjudication_colab_20261116.zip`。

先試跑：把步驟 2 的 `LIMIT` 改成 3，`MODELS` 只留第一個，幾分鐘可以確認整個流程。

## 要提交項目

把步驟 6 下載的 `adjudication_colab_20261116.zip` 放到 Mac 的 `local/evidence/live-mode-adjudication-20261116/colab/`。裡面有：

| 檔案 | 內容 |
| --- | --- |
| `REPORT.md` | 硬體規格表、模型表、結果表、要注意的地方 |
| `hardware.json` | GPU 名稱、記憶體、驅動版本；CPU 型號和核心數；RAM；磁碟；作業系統；Python |
| `ENV.json` | Ollama 版本、每個模型的 digest、載入時的 `ollama ps`、載入後的 GPU 記憶體 |
| `summary.json` | 每個模型和每種輸入：合法率、延遲 p50／p90、token、每秒輸出 token、答案分布 |
| `<模型>/calls.jsonl` | 每次呼叫一列：延遲、Ollama 的各階段時間、token、答案、理由、是否合法 |

Colab 上的報告沒有正確率。帶回來之後用下面的指令評分，會和 OpenAI 的結果放在同一張表：

```bash
python scripts/live_mode/adjudication_score.py --questions local/evidence/live-mode-adjudication-20261116/questions --calls <各個 calls.jsonl> --out <輸出.json>
```

## 針對 Colab 的限制做的處理

| 限制 | 處理 |
| --- | --- |
| 連線可能中斷 | 每答一題就寫進 `calls.jsonl` 並同步到磁碟。重新執行會跳過答過的題目，出錯的那幾題會重試。`ENV.json` 每跑完一個模型就寫一次 |
| 執行階段被回收後檔案會消失 | 沒有辦法避免，README 和筆記本都有說明。結果要在跑完後馬上下載 |
| 不保證分到 GPU，也不保證是 L4 | 沒有 GPU 就拒絕執行。GPU 型號和記憶體寫進報告；不是 L4 時報告會標出來 |
| 模型放不進 GPU 記憶體時 Ollama 會把一部分放到 CPU | 在真的有請求在跑的時候讀 `ollama ps`，不是 100% GPU 就在報告裡標出來 |
| 「沒有使用 GPU」的提示 | 筆記本開頭有說明：那個提示只看筆記本的 Python 程序，真正用 GPU 的是 `ollama serve` |
| 磁碟有限，模型很大 | 下載前檢查可用空間（少於 15 GiB 就跳過那個模型）；預設每個模型跑完就刪掉 |
| 下載有時會卡住或失敗 | 下載最多重試 3 次，失敗就跳過那個模型並寫進報告 |
| 沒有 systemd | 筆記本自己在背景啟動 `ollama serve`，重跑那一格不會重複安裝或重複啟動 |
| 新版 Ollama 的安裝檔需要 `zstd` | 安裝前先用 apt 裝 `zstd` |
| 第一次請求要載入模型，可能要幾分鐘 | 暖機請求另外給 10 分鐘的上限，結果不計入 |
| 長時間沒有輸出的格子看起來像當掉 | 每 6 題印一次進度 |
| 瀏覽器可能擋下載 | 自動下載失敗時印出檔案路徑，可以從檔案面板手動下載 |
| 重跑步驟 0 時路徑會疊進去 | 每次先回到 `/content` |
| 舊版 Ollama 的預設上下文長度可能切掉影像 | 明確設定上下文長度 4096 |

沒有處理的：Colab 的 GPU 配額用完、執行階段的最長時數。全部跑完預估不到 1 小時，應該碰不到。

## 沒驗證的部分

- 整個包沒有在真的 Colab 上跑過。Ollama 的安裝步驟、三個模型的下載、影像輸入、結構化輸出的格式，都沒有實測。
- `run_vision_probe.py` 用假的 Ollama 伺服器在 Mac 上測過：沒有 GPU 時拒絕、正常執行、中斷後接著跑、產生報告。假伺服器不會真的看圖。
- 筆記本的每一格只確認過語法正確，沒有執行過。
- 三個模型在 L4 上的延遲和記憶體用量都沒有數字。
- `llama3.2-vision` 支不支援 Ollama 的結構化輸出，沒有確認；不支援的話那個模型的合法率會很低，報告會顯示出來。
