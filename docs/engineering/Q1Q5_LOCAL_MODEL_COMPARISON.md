# Q1–Q5 本機模型比較（2026-10-23，依 #144 提案）

公開 locator 約定：`$AMIDST_ARTIFACTS` 代表審查者自行指定、canonical 絕對路徑的 LOCAL 證據根目錄，`$AMIDST_SOURCE`／`$SOURCE` 代表按 composition 還原的工程，`$AMIDST_PYTHON`／`$AMIDST_PYTHON_ENV` 代表既有 Python executable／環境。這些是去識別化 locator，不宣稱其他機器已存在對應資料；先取得相同 hash 的 LOCAL 檔案並設定環境變數。GitHub 只有公開程式與精簡收據，完整 RGB、錄製、模型 wire 與原始命令紀錄仍為 PRIVATE／LOCAL。文中的歷史數據未因路徑去識別化而重跑。

本次隔離測試顯示 Qwen3 1.7B 回覆較快，但尚不能取代 Qwen2.5 7B：兩者在這一組機械輸入都沒有可採用的 Q3 解析或 Q5 Agent 決策，2 秒 probe 也全部逾時。Qwen3 4B 因磁碟底線而未下載／未測。產品仍預設 RULE_ONLY，沒有啟用新模型或放寬 guard。

這是同一組 SYNTHETIC 輸入、不同 seed 的工程診斷，不是組員題目、標準答案、獨立測試集、正式正確率或完整 Demo 驗收。阻擋追蹤於 [#186](https://github.com/Polalalabear/amidst/issues/186)，程式與文件在 [PR #174](https://github.com/Polalalabear/amidst/pull/174)。既有 runtime 與診斷記錄見 [Q1Q5_QWEN_RUNTIME.md](Q1Q5_QWEN_RUNTIME.md)。

## 方法與邊界

- Apple M3、16 GiB；既有 Ollama 0.35.0，loopback `127.0.0.1:11437`。每組先確認無已載入模型，管理用空 prompt 預載獨立記時；完成後只釋放本次載入的模型記憶體，沒有重啟服務。
- native `/api/chat`、`format: json`；Q3 將原 template／closed catalog 放 system，解碼後的原始中文 USER_TEXT 放 user。Q5 沿用原 template，另列既有工具的精確 argument keys。兩模型採相同 framing、採樣與現有 parser／工具／guard。這不是 Ollama 原生 `tool_calls`：仍是專案的 JSON `{tool, arguments}` envelope。
- context 4096、輸出 cap 256 tokens、temperature 0.7、top_p 0.8、top_k 20、seed 7／8／9。1.7B 顯式 `think: false`，不修復 JSON、不移除 thinking／Markdown、不做隱藏 retry。非空 thinking、native tool_calls、截斷、錯誤模型直接拒絕。
- 長診斷：call 30000ms／total 90000ms；只修改記憶體中複製的 SYNTHETIC bindings，Q3 只嘗試一次，Q5 既有回合限制不變，來源檢查間隔 1000000us。fixture 的 APPROVED 只代表合成配置，不能當正式核定。
- 短 probe：兩模型各做 Q3／Q5 一次，call 2000ms／total 5000ms。D65 核准的是 **Q5 call 2000ms／total 5000ms**；**Q3 2000ms 仍是 PROPOSED**。本診斷不修改正式參數或契約。
- 每次 provider deadline 包含呼叫前後的模型 digest／共享 runner 檢查。每輪記 caller request、實際 wire request、模型與 template pins、raw output、native envelope telemetry、hash、拒絕原因和 replay。
- live session 與 offline replay 分別記時。Q3 replay 對同一 request／audit pin；Q5 用 recorded clock，核對 response output hash、逐筆 decisions 與 links。16／16 session 重播一致，不需要模型生成。
- 沒有 RT-DETR 同跑、真 RGB、正式 r004、GT、renderer trajectory 或人工題目／答案。其他桌面程序沒有被控制，因此不是一般硬體 benchmark。

native API 的 `format`／`think` 定義見 [Ollama chat API](https://docs.ollama.com/api/chat)；1.7B 模型模式見 [Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3-1.7B)。

## 模型與 pins

| 模型 | manifest/API digest | 狀態 |
| --- | --- | --- |
| qwen2.5:7b-instruct，Q4_K_M | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | 既有模型；新增 native-chat 對照 |
| qwen3:1.7b-q4_K_M | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` | 已下載，僅工程診斷 |
| qwen3:4b-instruct-2507-q4_K_M | `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` | SKIPPED_DISK_HEADROOM，沒有推論 |

1.7B 下載本身約 586.29 秒，與推論分開記錄。weights blob 為 1,359,279,776 bytes；manifest 宣告的所有 layer／config 大小與實際新增配置空間不等同，不能把它當 `df` 差值。

## 實測結果

下表是長診斷 **live 等待時間**，包含 provider、工具／guard 與 Q5 回合流程；預載與 offline replay 不包含在內。每列 N=3，是同一輸入的三個 seed。

| 模型／任務 | 三次等待秒數 | 中位等待秒 | 可採用結果 | 拒絕／兜底 |
| --- | --- | --- | --- | --- |
| Qwen3 1.7B／Q3 | 5.090、4.380、4.365 | 4.380 | 0/3 | INVALID_RESPONSE ×3 |
| Qwen3 1.7B／Q5 session | 11.931、10.100、10.136 | 10.136 | 0/3 | ROUND_LIMIT ×3 |
| Qwen2.5 7B native／Q3 | 30.006†、28.551、24.657 | 28.551 | 0/3 | TIMEOUT ×1、INVALID_RESPONSE ×2 |
| Qwen2.5 7B native／Q5 session | 30.014†、71.533、60.906 | 60.906 | 0/3 | TIMEOUT ×1、ILLEGAL_CANDIDATE ×2 |

† 逾時樣本是截至 deadline 的等待，不是成功完成耗時。含逾時的中位數也只描述本次觀測等待。Q5 各 session 呼叫數不同，不可用這些數字推廣為模型速度倍率；N=3 不報 P95。

Qwen3 1.7B 共 12 次 native envelope 完整，但 envelope 合法不等於任務有效。Q3 例如回傳錯誤 `time_literal` 型別，被既有 literal/schema 驗證拒絕；Q5 重複呼叫合法的 `get_observation_summary`，沒有完成候選證據／決策，三回合後兜底。Qwen2.5 native 共 10 次 provider 呼叫，其中 8 次完整、2 次 timeout；完整 envelope 仍未產生可採用任務結果。

只取已完成呼叫、依 server `eval_count/eval_duration` 計算的 decode tokens/s 中位數：1.7B Q3 21.64、Q5 21.29；7B native Q3 5.53、Q5 5.38。這不包含 prefill，也不是產品延遲／一般硬體能力保證。

2 秒 probe：1.7B Q3 2.006s、Q5 2.014s；7B Q3 2.005s、Q5 2.011s，四次都是 PROVIDER_TIMEOUT，沒有可採用結果。歷史 raw-generation Qwen2.5 Q3 14.726s 診斷使用不同 framing／採樣，保留在舊文件，不能與本表當純模型大小 A/B。

## 原 #127 與 focused 驗證

原測試包 pin `994d34c8340855dbf0e28d0273851049df5e6c7d`，未修改包、未使用 `--only`。兩模型 × 長診斷／短 probe × Q3／Q5 共 8 組代表輸出（各取 seed 7）：

- 四組 Q3 各 **56 PASS／0 FAIL**；這包含合法兜底回覆，不能當 LLM 解析成功。
- 四組 Q5 各 **133 PASS／14 FAIL／3 SKIPPED_NO_CONTEXT**。14 FAIL 沿 #145／#170 的 schema／records 差異，3 skip 是 SEARCHING_TRIGGER_TIME 缺 context；不冒充通過。Q5 evidence／snapshots 來自精確 offline replay，沒有新推論或改寫輸出。
- 新增 benchmark focused **22 PASS／0 FAIL**：native framing、forbidden fields、pins／owner、完整 deadline、無 retry、tamper、Q3 parser 與 Q5 工具／決策回合及 recorded replay；連同既有 API／runtime／diagnostics，四檔限定回歸 **110 PASS／0 FAIL**（`focused-combined.xml`）。

因此 PR 維持 **B／Draft**，不合 staging。新 benchmark 是工程 CLI，不被 runtime／launcher 匯入；沒有開放產品模型 allowlist、改變 RULE_ONLY、SWITCH guard 或錄製契約。

## 磁碟與未測項

4B manifest config＋layers 共 2,497,293,803 bytes。檢查時可用 10,262,147,072 bytes，扣除後不足 8,589,934,592 bytes（8 GiB）底線，因此未下載／未測。1.7B 下載最低可用 10,262,306,816 bytes，沒有觸發底線。

只做 cache 審計，沒有刪除：uv cache 因 symlink／owner 檢查不通過而跳過；npm `_cacache` 與 node-gyp 的配置空間合計 465636 KiB，單靠它們仍不足安全容納 4B。原 Qwen2.5 weights、Blender／r003／A／B1／GT 全部保留。`du` 是配置量，不是已回收量；最終 `df -k` 和本次新增 artifact／模型大小分別記錄。

尚未驗證 4B 品質／延遲、RT-DETR 併發、正式 r004、真 LLM→產品執行來源旗標、正式 Q3 timeout 或正式 Agent 成功。後續先改善 prompt 的 schema／工具狀態表達並重跑相同 guard；不因小模型較快就調寬產品預算或直接切換預設模型。

## 重現與 LOCAL 證據

`$AMIDST_ARTIFACTS/q1q5-model-compare-20261023/` 保存 `COMPARISON.json`、四組 `*-command.json`、原始 trial／wire／telemetry／replay、`conformance-summary.json`、原包報告、cache audit、前後 df。`CURRENT.md`／manifest 是最終 hash 入口；不含權重副本。

本 PR 尚依賴其他 Draft 的工程組成，單獨 checkout 不是完整 Demo。`source-delta/COMPOSITION_DELTA.json` 記錄本次三檔與前次 source 組成的精確 pins。限定命令示例（使用已按 manifest 還原的工程目錄；output 必須是不存在的新目錄）：

```sh
: "${AMIDST_ARTIFACTS:?set the LOCAL artifact root first}"
: "${AMIDST_PYTHON:?set an existing Python executable}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE/src" \
uv --no-cache run --no-project --offline \
  --python "${AMIDST_PYTHON:?set an existing Python executable}" \
  python "$SOURCE/scripts/benchmark_q1q5_local_models.py" \
  --synthetic --model qwen3:1.7b-q4_K_M \
  --model-digest 8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7 \
  --base-url http://127.0.0.1:11437 --output "$NEW_OUTPUT" \
  --repeats 3 --call-timeout-ms 30000 --total-timeout-ms 90000
```

這個 CLI 不下載權重；先驗模型 pin 與共享 runner 空閒。實際四條完整 argv 和1秒磁碟監測收據在 artifact `*-command.json`／`reproduce/run_compare.py`；原 #127 八條精確 argv 在 `conformance-summary.json`。重跑使用新路徑，不覆寫本次原始輸出。
