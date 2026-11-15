# 問題與解法紀錄 2026-11-15～16

這份文件記錄 2026-11-15～16（D220–D238）遇到的問題、根本原因、解法和證據。每一條都已用 `gh pr view`、`gh api` 和 [#93](https://github.com/Polalalabear/amidst/issues/93) 的留言核對過。查不到出處的寫 `UNKNOWN`。

- 寫於：2026-11-16，`main` @ `8b023775`
- 決策紀錄：[#93](https://github.com/Polalalabear/amidst/issues/93) D220–D238，下一個決策編號是 **D239**
- 8785 demo pin：`b24d6a26`（D235）

縮寫：「#93 D2xx」指 #93 上該決策的留言，連結列在文末的〈證據連結〉。

## 總表

| # | 問題 | 影響 | 根本原因 | 解法 | 狀態 | 證據 |
|---|---|---|---|---|---|---|
| 1 | 8785 更新閘門的 core-e2e 失敗（check 91；交接時記成 check 84 和 91） | 8785 無法從 `74b84463` 更新 | 換幀時 `img.src = url` 直接換圖，新圖載入前 `<img>.complete === false`，播放取樣剛好落在這段就失敗（競態），機器慢時更容易發生。check 84 其實通過：訊息在 assert 之前就組好，尾端的「failed」只是字串，交接時看錯了 | `frontend/workbench-v2/ui-shell.mjs` 新增 `showFrameImage()`：先用分離的 `Image` 預載，載好才換到可見的 `<img>`。斷言沒有放寬。CPU 降速 4 倍（CDP `setCPUThrottlingRate=4`）可以重現，修好後 core-e2e 130/130 通過 | 已修 | [#542](https://github.com/Polalalabear/amidst/pull/542)，merge `b24d6a26`（head `0a0b644f`）；#93 D229、[#542 實際產出](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892877838)、[審查](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892934457) |
| 2 | `scripts/local/env_templates.sh build` 中途失敗 | 本機環境模板建不起來 | 在 `set -euo pipefail` 下，`relocate` 和 `abs_left` 裡的 `grep` 找不到東西會 exit 1 | 把 `grep` 找不到（exit 1）當作成功 | 已修 | [#542](https://github.com/Polalalabear/amidst/pull/542)，commit `0a0b644f`，merge `b24d6a26` |
| 3 | WP5 實跑時呼叫 OpenAI 沒有經過 `ApiGuard`（#538 審查的 P1，也是 #537 留下的 P2 #5） | 付費呼叫沒有帳本、沒有每日／每分鐘上限，也不看伺服器開關 | DP1/DP3 的 `OpenAIProvider.call` 和 NL 的 `OpenAINlClient` 只經過程序內的 `LocalCapGuard` | 新增 `wp5_runner.make_api_guard`：用 `--approved-usd` 當總額上限，價格取自 PINNED 價目表，所有呼叫都經過 `ApiGuard` | 已修 | [#538](https://github.com/Polalalabear/amidst/pull/538) head `b95c3bb3`，merge `18715e69`；[審查留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892771547)、#93 D223、D225 |
| 4 | `ApiGuard` 預設每日 200 次、每分鐘 10 次，WP5 pilot 要 288 次 | pilot 跑到一半會被護欄擋下 | 這是 #537 的預設值，沒有配合 pilot 的呼叫量調整 | 寫進 `docs/evaluation/WP5_DRYRUN_ESTIMATE_20261115.md`：實跑前先調高 `AMIDST_API_MAX_CALLS_PER_DAY`、`AMIDST_API_MAX_CALLS_PER_MIN`、`AMIDST_API_USD_PER_DAY`。OpenAI 試跑用了 `AMIDST_API_USD_PER_DAY=3`、`MAX_CALLS_PER_DAY=60` | 已記錄（每次實跑前都要調） | [#538](https://github.com/Polalalabear/amidst/pull/538)；#93 D223；[OpenAI 試跑紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6900077258) |
| 5 | 事件檢視器裡 A4-1-8CAM／B4-1-8CAM 顯示 UNAVAILABLE | 8 鏡頭的 run 看不到 | `start_all_demo.command` 啟動事件檢視器時沒有帶 `--root-8cam`；8785 的伺服器本來就沒有 8CAM run | `start_all_demo.command` 加上 `--root-8cam`。有帶和沒帶的對照日誌在 LOCAL（見〈LOCAL 證據〉） | 已修 `.command`。延後：`start_all_demo.ps1` 還沒同步；`.command` 裡的啟動時間註解過時（D234 P2）。8785 新 UI 要不要加 8CAM run：待使用者決定 | [#545](https://github.com/Polalalabear/amidst/pull/545) head `4eba50b8`，merge `8b023775`；#93 D234、[#545 準備紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6893238899) |
| 6 | 8785 要從 `74b84463` 更新 | demo 停在舊版 | — | 在 `b24d6a26`（tree `ca6d0687`）上跑完閘門：unit node 576、pytest 2633、dependency、HTTP、core-e2e 130、real-e2e 900 和 1300 各 347，全部通過。使用者照 #545 的 `docs/operations/DEMO_8785_UPDATE_PLAN_20261115.md` 更新，pin approve 和 check 都 exit=0，HTTP 200。pin 用 `b24d6a26`，不用含 #545 的 commit：#545 改的 `start_all_demo.command` 不在 8785 的執行路徑上（8785 走 `start_445_demo.command`），等下次更新 pin 時和 #543 一起帶進來，不必重跑閘門（D234 方案 a） | 已完成 | #93 D234、D235；[#545](https://github.com/Polalalabear/amidst/pull/545)；舊 pin 備份 LOCAL `local/demo-pin.74b84463.bak.json`（SHA-256 UNKNOWN） |
| 7 | 即時模式：MPS 上 3 鏡頭×5 fps 跟不上（實際 1.9–2.2 fps） | 原本的設定不能用來 demo | 瓶頸是偵測器的 forward。CPU 每張 345–430 ms，比 MPS 慢 3–5.6 倍 | 改用實測撐得住的設定（N6×烘焙場景，320×180）：3 鏡頭×2 fps（丟 1%，p50 約 240 ms）、2 鏡頭×3 fps（丟 3/150，p50 約 160 ms）。2 鏡頭×4 fps 會丟 20–24%，撐不住 | 已量測；#544 還是 Draft，未合併 | [#544](https://github.com/Polalalabear/amidst/pull/544) `docs/evaluation/LIVE_MODE_SPIKE_20261115.md` §2、§3、§5、§10.3；#93 D230、D236 |
| 8 | N6 整合後變體材質渲染失敗（`material.onBeforeRender is not a function`） | T/A/B/C 的服裝變體顯示不出來 | `SkeletonUtils.clone` 用 JSON 複製 `mesh.userData`，裡面的材質因此變成普通物件 | 改把變體表以 mesh 名稱存進 `gltf.userData.variantTable`；測試也檢查複製後仍是真正的材質 | 已修（在 #544，未合併） | [#544](https://github.com/Polalalabear/amidst/pull/544) commit `971b9763`，報告 §10.1；[N6 整合紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6893414668) |
| 9 | 偵測率不夠高 | 即時模式在部分鏡頭追不到人 | 膠囊人形分數大多落在 0.1–0.35，偵測器不把它當人。N6 在烘焙場景比在 spike 場景低 14.7 點，推論是場景對比低、偏暖、沒有人物陰影（未單獨驗證） | 換成 N6 人物：膠囊 16.7%，N6 WIP 60.6%，N6×烘焙場景 69.1%（N6×spike 場景 83.8%，膠囊×烘焙場景 25.6%）。CAM_ENTRY 19%、R101_IN 47% 仍偏低 | 部分改善。協調者建議做半天的真人模型對照實驗（CC0 真人模型、場景加影子）：待使用者決定 | [#544](https://github.com/Polalalabear/amidst/pull/544) 報告 §4、§10.2；#93 D236 |
| 10 | N6 烘焙場景的天花板比 #529 亮，看得到接縫（#539 審查 P2-1） | 和錄影畫面外觀不同，可能影響偵測 | 烘焙光照：七鏡頭平均 luma 高 3～15/255，W1 低 16 | 使用者採用 N6 外觀，天花板和接縫之後再調 | 延後（D227） | [#539](https://github.com/Polalalabear/amidst/pull/539) merge `1aea09cd`；[審查留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892804301)；#93 D227 |
| 11 | WP5 Colab v1：DP1/DP3 共 96 題全部 `PROVIDER_UNAVAILABLE`，大約 35 ms 就退回規則 | 模型完全沒被呼叫，v1 的 DP 結果作廢 | 推論：送給 Ollama 的 `format` schema 裡，`candidate_id` 的 `$ref: #/$defs/opaque_id` 懸空，又含 Ollama 不支援的 `if/then/else/not/uniqueItems`，回 HTTP 400；`OllamaProvider` 把 4xx 當成 `UNAVAILABLE`，`decide()` 不重試就退回規則。NL 的 schema 是自包含的，所以不受影響 | `ollama_format_schema()` 把 `$ref` 內嵌展開，拿掉不支援的關鍵字，回應端仍由 `validate_response` 把關。provider 會記 `last_error`。只要某個題型 100% `PROVIDER_UNAVAILABLE`，整次執行就標 `FAILED`。Colab v2 確認 DP1/DP3 都有呼叫模型 | 已修（#546 開著，可以合併：D238） | [#546](https://github.com/Polalalabear/amidst/pull/546) commit `1068cce5`、`fae92353`；[#546 紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6896302382)、[審查](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6896384905)；#93 D235、D236、D238 |
| 12 | Colab 顯示「沒使用到 GPU」 | 看起來像是沒用到 L4 | 這個提示只看筆記本自己的 Python 程序，而它不用 CUDA；模型在另一個 `ollama serve` 程序裡跑。v1 又幾乎沒有題目真的進到模型 | 筆記本開頭和步驟 6 加上說明：要看 `ollama ps`（`100% GPU`）和 `nvidia-smi`。暖機後不是 100% GPU 就停 | 已修（說明在 #546）；GPU 是否真的有用到，見第 13 條 | [#546](https://github.com/Polalalabear/amidst/pull/546)（`docs/operations/WP5_COLAB_L4_README.md`、`notebooks/agent_decision/wp5_colab_l4.ipynb`）；#93 D235 |
| 13 | Colab v2：`INVALID_RESPONSE` 偏高（qwen 17–21%、llama 63–71%）；`ollama_ps` 只抓到表頭，GPU 沒被證實；NL rule_agree 0/24 | v2 的結果 `run_status=WARN`，還不能當正式數字 | 格式錯誤的原因：UNKNOWN。`ollama ps` 抓取的時機不對（推論）。NL 指標疑似寫錯（未確認） | session `wp5-calib-finish` 修格式錯誤率、`ollama ps` 抓取時機和 NL 指標，再重產一鍵筆記本 v3 | 進行中 | #93 D238 |
| 14 | OpenAI：repo 裡的 `api_model_id` 是 null，模型名稱對不上 | runner 會送 `model="astra6"` 這種不存在的 id | `configs/q1q5/agent_decision_params_v1*.json` 沒有填 API id，runner 也沒有把 params 傳給 provider | 使用者給了對應（D237）：astra6 → `gpt-6-astra`、sol6.1 → `gpt-6.1-sol`、terra6.1 → `gpt-6.1-terra`，預設 terra。試跑上限 USD 3（D233）。實際花費 USD 0.1025（PINNED 價目，31 筆有用量的呼叫）；護欄帳本的估計上界約 USD 0.136。另外 OpenAI 不接受原本的回應 schema（含 `if`），改送內嵌 schema、`strict:false` | id、價目和報告已推到 #546 的 `f1ebdded`；收尾在 `wp5-calib-finish` 進行中。待決定：formal 的 2 s 逾時（p50 2.7–4.7 s 全部超過）和正式額度（A USD 4／B USD 12／C USD 46） | [#546](https://github.com/Polalalabear/amidst/pull/546) commit `f1ebdded`（`docs/evaluation/WP5_OPENAI_CALIBRATION_20261115.md`）；#93 D233、D237、D238、[試跑紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6900077258)；帳本 LOCAL `local/evidence/wp5-openai-calib-20261115/guard-ledger/usage.jsonl`（9,374 B，SHA-256 `c4d88c31…3ea6`，完整值見該資料夾的 `SHA256SUMS`） |
| 15 | 本機資源吃緊：M3 8 核、16 GB；同時跑閘門和量測時 load 到 24，磁碟降到 8.3 GiB | 碰到程式內建的 8 GiB 保護線；高負載下量出的延遲不可靠 | 好幾個 session 同時跑閘門、量測和 clone | 8785 閘門跑完之前不開第 3 個寫檔 session；高負載下量的即時模式延遲標成「僅供參考」（D232）。清掉 4 個已結束 session 的 scratchpad：協調者的說法，GitHub 上沒有紀錄（UNKNOWN）。「demo 時不同時跑測試、延遲量測要記 load1」：D232 只寫了前兩點，這兩條規則的出處 UNKNOWN；#544 的量測紀錄有記 load1（8–13） | 已處理；規則持續有效 | #93 D232；[#544 實際產出](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892891079) |
| 16 | 兩個 session 用完 5 小時額度，中途停下 | 工作中斷；OpenAI 試跑的改動一度沒有推上去 | 長任務沒有分段 commit | `live-n6-integrate`：commit 已推到 #544（D235）。`wp5-openai-calib`：D238 寫的時候還沒推；之後的 commit `f1ebdded`（2026-11-15T19:33:08Z）已推到 #546。剩下的收尾交給新 session `wp5-calib-finish`。教訓：長任務要分段 commit、分段 push | 已處理；教訓要寫進之後的 brief | #93 D235、D238、[試跑紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6900077258) |

## 待使用者決定

- 8785 新 UI 要不要加 8CAM run（第 5 條，D234）。
- 真人模型對照實驗：半天，CC0 真人模型加場景影子（第 9 條，D236）。
- OpenAI 的 formal 逾時（2 s）要不要放寬，以及正式額度 A／B／C（第 14 條）。

## 延後項

- `start_all_demo.ps1` 同步 `--root-8cam`；`.command` 的啟動時間註解（第 5 條）。
- N6 烘焙場景的天花板亮度和接縫（第 10 條，D227）。
- 下次更新 8785 pin 時帶上 #543、#545（第 6 條，D234）。

## LOCAL 證據

| 路徑（相對 `local/`） | 內容 | SHA-256 | 可否重建 |
|---|---|---|---|
| `evidence/demo-update-prep-20261115/gate-20261115-1829/` | 8785 閘門結果、`ev-no8cam.log`、`ev-with8cam.log`、截圖 | `ev-no8cam.log` `4bcd67f863fba15f8c0a63e802d57fa8fa7348817651854be6cd19c941d8eeea`；`ev-with8cam.log` `f62bcb7da347847e1502c519804f2da0a347ab0bc79f1b39026a8d76500dfe55`；其他見 #545 的 `DEMO_8785_UPDATE_PLAN_20261115.md` §2 | 可以，在 `b24d6a26` 上重跑閘門（約 24 小時有效） |
| `demo-pin.74b84463.bak.json` | 8785 舊 pin 的備份 | UNKNOWN | 不適用 |
| `evidence/live-mode-spike-20261115/lat/*.latency.json` | MPS 延遲矩陣（5 份） | 見 #544 報告 §7 | 可以，用 `measure/latency.mjs` 重量（數字會因機器負載而不同） |
| `evidence/live-mode-n6-20261115/` | N6 偵測率和延遲（含逐樣本 rows） | 見 #544 `docs/evaluation/live_mode_n6_20261115/SHA256SUMS.txt` | 可以，用 `measure/run_n6.sh` 重量 |
| `data/wp5-packs-20261115/oneclick/wp5_colab_oneclick.ipynb` | 一鍵 Colab 筆記本 v2 | `fa7bb3721e146811589052835f8dc7ec586f860a6da337369e25e187f22cb8ec` | 可以，用 `scripts/agent_decision/build_oneclick_notebook.py`（#546） |
| `evidence/wp5-openai-calib-20261115/` | OpenAI 試跑帳本和結果 | `guard-ledger/usage.jsonl` `c4d88c31…3ea6`；`SHA256SUMS` `5a5b97cb…b620`（完整值在資料夾內） | 不能（付費呼叫的實際回應） |
| Colab v1／v2 回傳資料 | Colab 執行結果 | UNKNOWN（放在使用者的下載資料夾，不在 `local/` 內） | 不能 |

## 證據連結

| 決策 | #93 留言 |
|---|---|
| D220–D222 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892705890 |
| D223–D224 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892791456 |
| D225–D226 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892820740 |
| D227 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892835761 |
| D228 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892865295 |
| D229 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892919710 |
| D230 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892941990 |
| D231 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6892973039 |
| D232 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6893131115 |
| D233 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6893200857 |
| D234 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6893367381 |
| D235 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6896200872 |
| D236 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6896755481 |
| D237 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6896849150 |
| D238 | https://github.com/Polalalabear/amidst/issues/93#issuecomment-6900057137 |

| PR | 狀態（2026-11-16） | merge／head |
|---|---|---|
| [#537](https://github.com/Polalalabear/amidst/pull/537) API 預算護欄 | 已合併 | `57dd761b` |
| [#538](https://github.com/Polalalabear/amidst/pull/538) WP5 harness | 已合併 | `18715e69`（head `b95c3bb3`） |
| [#539](https://github.com/Polalalabear/amidst/pull/539) N6 素材 | 已合併 | `1aea09cd` |
| [#540](https://github.com/Polalalabear/amidst/pull/540) 交接 11-15 | 已合併 | `52b3ab2b` |
| [#541](https://github.com/Polalalabear/amidst/pull/541) DP4 API／Agent | 已合併 | `80f36220` |
| [#542](https://github.com/Polalalabear/amidst/pull/542) core-e2e 修正 | 已合併 | `b24d6a26`（head `0a0b644f`） |
| [#543](https://github.com/Polalalabear/amidst/pull/543) WP5 資料包 | 已合併 | `4972f0f9` |
| [#545](https://github.com/Polalalabear/amidst/pull/545) 8785 更新計畫 | 已合併 | `8b023775`（head `4eba50b8`） |
| [#544](https://github.com/Polalalabear/amidst/pull/544) 即時模式 | Draft | head `2b14a84e` |
| [#546](https://github.com/Polalalabear/amidst/pull/546) WP5 Colab 修正／OpenAI 試跑 | 開著 | head `f1ebdded` |
| [#547](https://github.com/Polalalabear/amidst/pull/547) 即時模式 LLM 決策設計 | Draft（使用者開的） | head `34683b9c` |
