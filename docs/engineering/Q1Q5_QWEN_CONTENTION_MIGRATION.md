# Qwen3／RT-DETR 實測、改善與遷移評估（2026-10-23，依 #144 提案）

本次完成：只讀遷移評估、三組實際資源對照、完全卸載Qwen的額外RT對照、v2 schema／工具進度實作、原預算與長診斷／replay驗證。**沒有正式遷移舊state／DB、沒有啟動產品server、沒有證明Agent已能有效追蹤。** 原始負面實驗保留，不把較長診斷當正式預算通過。

結論：生成期間RT-DETR吞吐顯著下降，單純常駐模型的影響在這輪很小；併發區間沒有新增swap或swapin/out。Q3的型別／原文問題可藉封閉詞表與schema改善，但輸出tokens增加、等待變長。Q5從重複工具變成合法返回，仍沒有Agent切鏡，追蹤效用未驗證。現有2秒呼叫／5秒總預算仍不滿足。

## 量測條件與界線

- Apple M3／16GiB；Ollama0.35.0，既有 `127.0.0.1:11437`，Qwen3 1.7B Q4_K_M manifest/API digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`。沒有下載任何權重，Qwen2.5已移除且沒有恢復。
- 官方RT-DETR R18，code `df2a96c8c3a098567a1149bf0248da6efe6d495d`，weights SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`，torch2.6.0／CPU／2threads／FP32，輸入640×640。重用既有deps；沒有安裝新套件或改官方source。
- 八個不同鏡頭各一張既有r004 preview RGB輪替（CAM_WIDE取已選90°），只讀RGB bytes；非正式A4/B4事件run。先解碼八張圖，計入每張resize／forward／postprocess，不計檔案讀取與預載；單一worker無sleep飽和跑，非九鏡頭即時流。
- 每組順序：Qwen常駐閒置→RT單跑（Qwen仍常駐但不生成）→Qwen單跑→並跑，穩態至少30秒；另外完全卸載Qwen再跑RT。RT預載與一張warmup在resource trace中另標，不進forward統計。
- Qwen只用固定SYNTHETIC Q3／Q5輸入，各重複3次，temperature0、seed7、context4096、cap256、think=false；不是三題／正式accuracy。資源對照每次provider允許30秒，僅診斷；未放寬產品Q5 D65 call2000ms／total5000ms，Q3 2000ms仍PROPOSED。
- 約每0.5–1秒採樣process RSS、vm_stat（實測page16384bytes）、swapusage、memory_pressure -Q、Ollama api/ps。RSS、API size_vram和系統壓縮頁是不同量，不相加冒稱實體RAM。
- 其他桌面程序不停止，phase順序未隨機化，也沒有GPU利用率／頻寬／溫度profile。因此可報觀測差異，不能精確歸因CPU排程、頻寬、thermal或宣稱一般硬體benchmark。P95僅N≥30，全部逐次值保留。

## RT-DETR實際容量

| 條件 | 張數N | 每張中位ms | phase吞吐fps | worker CPU秒/牆鐘秒 |
| --- | ---: | ---: | ---: | ---: |
| Qwen完全卸載 | 96 | 295.62 | 3.129 | 1.87 |
| 原模板：Qwen常駐、無生成 | 97 | 296.92 | 3.108 | 1.86 |
| 原模板：並行生成 | 19 | 1987.79 | 0.619 | 0.99 |
| 最終v2：Qwen常駐、無生成 | 95 | 300.75 | 3.114 | 1.88 |
| 最終v2：並行生成 | 32 | 1854.11 | 0.554 | 1.13 |

完全卸載與常駐無生成都約3.1fps；原模板生成期間降至0.619fps，最終v2生成期間0.554fps，後者相對同組無生成下降約82.2%。CPU秒／牆鐘秒由約1.88降至約1.13，支持生成時有明顯的共享資源競爭；未量測的底層機制仍UNKNOWN。

若需求是9台各5fps，總需45fps；此單worker本次離線容量約3.1fps，生成時約0.55fps，**不支持直接宣告可即時跑9台**。即使單台5fps也高於本次量測吞吐。這是容量對比，不是正式多鏡頭runtime驗收或偵測正確率。

## 記憶體與swap：實際數字

單位MiB；下表是穩態採樣峰值／差分，未把模型size_vram加入RSS。

| 條件 | RT RSS峰值 | Qwen runner RSS峰值 | 系統compressor峰值 | swap使用起→迄 | swapin/out新增 | pressure free最低% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen完全卸載 | 759.1 | 0.0 | 4004.7 | 2961.0→2961.0 | 0.06/0.00 | 60 |
| v2 RT單跑／Qwen常駐 | 653.4 | 1835.2 | 3917.1 | 2961.0→2961.0 | 0.00/0.00 | 49 |
| v2 Qwen單跑 | 0.0 | 2082.7 | 3769.7 | 2961.0→2961.0 | 0.00/0.00 | 49 |
| v2並行 | 693.6 | 2075.9 | 4236.9 | 2961.0→2961.0 | 0.00/0.00 | 46 |

`memory_pressure -Q`的free百分比是系統可回收／可用狀態指標，**不是空閒實體RAM百分比**。vm_stat真正Pages free最低曾僅約56MiB，不能單靠這一數字判定記憶體耗盡；同時要看壓縮、swap活動和pressure指標。Qwen API回報size_vram固定約1786.6MiB／context4096，與runner RSS有共享／映射關係，不能重複相加。

開始前已有約2.91GiB swap；測量期間多數穩態為2961MiB。兩個主要並行階段swap使用差、swapin與swapout均為0，故**這輪沒有證據把RT降速歸因於新swap I/O或swap擴張**。這不等於系統無記憶體成本，也不證明更長／更多模型負載仍安全。

## Qwen輸出改善與成本

| 固定單次輸出測試 | 原模板單跑中位s | 最終v2單跑中位s | 最終v2並跑中位s |
| --- | ---: | ---: | ---: |
| Q3一次解析 | 4.907 | 6.691 | 7.685 |
| Q5第一次模型輸出 | 3.893 | 10.454 | 11.428 |

Q5原模板是工具請求，v2是完整返回決策，輸出任務大小不同，不宣稱純模型速度比。Q3輸出token93→128；Q5首次輸出75→185。新schema／完整ID／固定audit欄位增加token成本，單靠禁止重複工具無法達到2秒。

初版schema實驗 `guided/` 只修正型別，仍漏class且把時間填date，Q5返回理由過長；其單跑中位Q3 6.947s／Q5 10.523s。這些負面數據和當時source保存在 `experimental-guidance-source/`，沒有抹掉再挑漂亮結果。

最終實際controller長診斷（call30s／total90s，複製SYNTHETIC bindings）三次：Q3 **3/3**通過原validator，session中位6.428s；Q5 **3/3**有合法Agent決策、每session兩次RETURN_TO_ORIGIN，中位20.790s，**0次Agent SWITCH**。不是正式accuracy、不是追蹤成功，不能以「合法返回」取代有效跟隨。

最終原預算probe：Q3與Q5都PROVIDER_TIMEOUT，規則接管；replay一致。因此v2是明確版本化、供review／對照的profile，沒有提升正式budget或證明即時Agent可用。預設Demo仍RULE_ONLY，既有v1設定檔沒有被就地改寫。

## 實作內容及保留邊界

- 新 `q3_parse_v2.txt`／`q5_agent_v2.txt`，保留v1。Q3給完整JSON Schema；可填class/color/camera/region值只取已存在server aliases在USER_TEXT中出現的原文片段，時間／日期用既有versioned lexical patterns，不餵人類答案。原文大小寫保留。這是程式協助縮小輸出空間，不能宣稱模型獨立語意能力提高。
- Q5明列phase、已完成工具、當前candidate、合法下一步與citation refs；decode schema不再提供重查context／observation，仍允許返回。現有工具dispatch／guard、SWITCH強證據與entry、NEXT非空引用、候選順序、round／timeout完全不改。無觀測NEXT與LOST時限仍待§14決定。
- rationale使用固定動作標籤，**不是模型自由推理或新的證據**。模型選action；controller保留全部pins／guard並執行。這次沒有實作「compact decision由server擴展長IDs」或「一律先預取候選再問模型」的新mode。
- native v2記 `q-demo.ollama-native-chat.v2`＋完整wire schema／hash；v1/raw replay保持。Q3模板版本顯式傳遞，診斷按已驗file pin的原audit版本選模板，schema建構也計入單次deadline。
- Q5/shared helper更新在原[PR #172](https://github.com/Polalalabear/amidst/pull/172)，head `1bb4135965fb53643e9fbbaf8e41fd77e8ffb9c8`；runtime／Q3／量測在[PR #174](https://github.com/Polalalabear/amidst/pull/174)，依賴前者，沒有把整個Agent重複加入HTTP PR。兩者B／Draft，未merge。

## 遷移評估

只讀pin了舊phase1五檔（啟動command、start_local_demo、local_agent provider／contracts、agent_provider.json），保存在 `MIGRATION_AUDIT.json`，沒有查改DB、state或另一checkout。舊config仍指向已刪的2.5，啟動器找不到模型會拒絕。

| 項目 | 舊phase1 | 新Q線 | 遷移判斷 |
| --- | --- | --- | --- |
| Ollama服務／store | 既有11437與同一模型庫 | 同一loopback，可pin Qwen3 | 可沿用，核對owner／digest；不重啟／複製權重 |
| Agent輸出 | ModelAction kind=tool/clarification/answer/refusal | Q5 SWITCH/NEXT/RETURN＋typed tools | 不相容，不能只改model tag |
| 預算／context | timeout120秒、8192ctx、keepalive10m、未設think | Q5 call2秒／total5秒、4096ctx、think=false | 不複製舊值，不默默放寬新契約 |
| 啟動／state | PG＋舊state＋python -m amidst.workbench | Office Application＋唯一run registry／media pins／recording | 建新Q線入口；不把舊state當r004 inference來源 |
| 資料／UI | 舊資料與其流程 | primary frontend/workbench與Q API；其他Draft UI仍待整合 | UI路徑／授權／媒體驗收另做，不把靜態頁當runtime |

建議遷移順序：先凍結完整工程source與recorded replay入口，再接approved run/index/graph/parameter/clock/media registry，明填四個registry/runtime環境變數與獨立file pins；先驗bootstrap、同origin/session/scene、media grants與無模型replay，再做真模型及瀏覽器驗收。缺registry仍NOT_READY，不能用合成fixture補成正式Demo。此處未產生假的可啟動正式registry或宣告完成遷移。

實測顯示，即使遷移入口完成，RT容量與2秒Agent預算仍是獨立阻擋。近期可交付的仍是RULE_ONLY／recorded replay；即時Agent需先處理輸出體積與RT調度，並補量測。只以減少模型常駐記憶體作解方，與本輪數據不符。

## §14待決選項（未分配正式編號，未實作）

1. compact Agent輸出由server依當前已pin的context擴展完整IDs／hash，保留raw→expanded映射與guard；用來減少185-token決策成本。需契約review，不能當成已准schema或output repair。
2. 候選證據由controller先備妥，Agent只判一次action，與原sequential tools並列比較；不能繞過證據／citation或把候選先驗當觀測。
3. RT與LLM生成的調度／取樣策略及CPU/MPS相容性另做實測；本次未更改正式裝置、採樣率、Q5預算或未核定的LOST時限。

## 驗證與重現

工程組成focused **270 PASS**；#172原typed-tools／Agent focused另 **56 PASS**（有重疊，不相加）。全部長診斷6筆response/journals、歷史2.5 Q3/Q5都在最終source以0模型呼叫精確重播；12個最終實測wire payload與最終builder相同，包含大小寫／deadline修正後的驗證。

原#127 pin `994d34c8340855dbf0e28d0273851049df5e6c7d` 全包未改、沒有--only：長診斷Q3 56 PASS；Q5 148 PASS／15 FAIL／4缺context。原預算Q3 56 PASS；Q5 133 PASS／14 FAIL／3缺context。長診斷多一筆decision導致同類D69 counter schema多一FAIL；links/counters/classifier差異沿#145/#170，未隱藏。初次exporter未配對的report保留，後以新檔名配對而不改domain bytes；配對收據可核對。SEARCHING_TRIGGER_TIME缺context仍不是PASS。

LOCAL `/Users/polalabear/amidst-artifacts/q1q5-qwen3-contention-20261023/CURRENT.md` 是最終入口；包含MEASUREMENTS、每次wire／envelope／逐張timing／resource JSONL、來源pins、COMMANDS、CONFORMANCE-FINAL、REPLAY_FINAL_SOURCE、WIRE_FINAL_SOURCE、MIGRATION_AUDIT與source delta。模型／媒體沒有複製。每次產製前後df，量測監測8GiB門檻，結束釋放本次模型記憶體，既有服務不重啟。

重跑範例（`SOURCE`為按composition還原的完整工程；config必須新建／核對pin，output必須新目錄）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE/src:/private/tmp/amidst-q1q2-d63-20261020/deps" \
uv --no-cache run --no-project --offline \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python \
  python "$SOURCE/scripts/measure_q1q5_contention.py" \
  --config /Users/polalabear/amidst-artifacts/q1q5-qwen3-contention-20261023/measurement-grounded-config.json \
  --config-sha256 e62471745a9376cd59796ed5f1e7aa09fd119944406182ea8d86abe47384e584 \
  --output "$NEW_OUTPUT" --profile guided
```

deps／upstream仍是LOCAL既有環境，沒有聲稱永遠存在；RT weights與preview輸入須按config pin核對。舊2.5推論需重新下載，歷史replay不需模型。正式r004／G4/G6、人工題目答案、正式準確率、真LLM下游provenance與Claude瀏覽器驗收仍分開未完成。
