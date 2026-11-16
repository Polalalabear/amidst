# 影像裁決測試：Colab 本機視覺模型

- 產生時間（UTC）：2026-11-16T02:42:36Z
- 題數：36；每題跑 image, text
- 這份報告沒有正確率：題目包不含標準答案，正確率回到 Mac 上評分。

## 硬體規格

| 項目 | 值 |
| --- | --- |
| GPU | NVIDIA L4 |
| GPU 記憶體 | 23034 MiB |
| GPU 驅動 | 580.82.07 |
| GPU 數量 | 1 |
| CPU | Intel(R) Xeon(R) CPU @ 2.20GHz |
| CPU 邏輯核心 | 12 |
| RAM (GiB) | 53.0 |
| 磁碟可用 (GiB) | 233.2 |
| 作業系統 | Linux-6.6.159+-x86_64-with-glibc2.39 |
| Python | 3.13.16 |
| Ollama | ollama version is 0.40.16 |

## 模型

| 模型 | digest | 載入時 `ollama ps` | 載入後 GPU 記憶體 |
| --- | --- | --- | --- |
| qwen2.5vl:7b-q4_K_M | 5ced39dfa4bac325dc1 | 100% GPU | 6640 MiB |
| qwen3-vl:8b-instruct-q4_K_M | 70e58e37beb15464e19 | 100% GPU | 7096 MiB |
| llama3.2-vision:11b-instruct-q4_K_M | 6f2f9757ae97e8a3f8e | 沒抓到 | 0 MiB |

## 結果

延遲只算格式合法的回答。

| 模型 | 輸入 | 呼叫 | 合法率 | 延遲 p50 (ms) | 延遲 p90 (ms) | 輸入 token | 輸出 token | 輸出 token/秒 | 答案分布 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| llama3.2-vision:11b-instruct-q4_K_M | 看圖 | 36 | 0.0 | None | None | None | None | None | {} |
| llama3.2-vision:11b-instruct-q4_K_M | 文字特徵 | 36 | 0.0 | None | None | None | None | None | {} |
| qwen2.5vl:7b-q4_K_M | 看圖 | 36 | 1.0 | 1439 | 1471 | 1176 | 23 | 47.2 | {"1": 26, "2": 10} |
| qwen2.5vl:7b-q4_K_M | 文字特徵 | 36 | 1.0 | 542 | 593 | 378 | 18 | 46.7 | {"1": 26, "2": 6, "3": 1, "0": 3} |
| qwen3-vl:8b-instruct-q4_K_M | 看圖 | 36 | 1.0 | 1699 | 1742 | 1176 | 23 | 43.3 | {"1": 24, "2": 10, "3": 2} |
| qwen3-vl:8b-instruct-q4_K_M | 文字特徵 | 36 | 1.0 | 698 | 784 | 378 | 24 | 46.8 | {"1": 13, "2": 17, "0": 6} |

## 要注意的地方

- llama3.2-vision:11b-instruct-q4_K_M：`ollama ps` 不是 100% GPU（沒抓到），延遲不能當 GPU 上的結果。
- llama3.2-vision:11b-instruct-q4_K_M（image）：合法率 0.0，低於 0.9。
- llama3.2-vision:11b-instruct-q4_K_M（text）：合法率 0.0，低於 0.9。
