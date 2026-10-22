# Q1–Q5 Agent 職責與雙模式比較

依使用者在 #184 對應 chat 的新指示，兩種 Q5 方式均做工程試用；這不是核定正式追丟門檻或辨識品質。依 #144 提案，原 #127／#135 不動。

## Agent 在整個 Q1–Q5 系統做什麼

| 系統階段 | 執行者與責任 |
| --- | --- |
| Q3 理解自然語言 | 規則 parser，或可選 LLM 將文字轉結構化條件／提出釐清。解析模型與切鏡 Agent 是不同職責；不找影像、不產生答案。 |
| RT-DETR／HSV | 程式對已授權 RGB 離線產索引，偵測人物／類別及顏色線索；LLM 不逐格看圖。 |
| Q1 找相機 | 程式查安全索引，保留相符／不相符／未評估；不需要切鏡 Agent。 |
| Q2 同鏡頭追蹤／失聯觸發 | 後端按來源取樣時間做局部連接與狀態機，無支持進入搜尋；不由 Agent 持續監看。 |
| 候選圖與排序、Q4 證據 | 程式按凍結圖／參數產生有界 top-k，聚合觀測支持；Agent 不能自行擴大、重排、改門檻或讀 GT。 |
| Q5 AGENT_SEQUENTIAL | Agent 讀搜尋摘要、當前候選證據及已曝光觀測，提交 SWITCH／NEXT_CANDIDATE／RETURN_TO_ORIGIN。實際切鏡仍由後端重新驗 guard、pin、來源時間。 |
| Q5 BACKEND_FLAGS 實驗 | 使用現有 RULE_ONLY Controller 做選擇，事件 adapter 產 FOUND／LOST；切鏡／提示是決定性的事件處理，不呼叫 Q5 LLM。 |
| 故障兜底、UI、replay、評分 | 程式執行；Agent 壞掉時規則接手餘下 session。人工題目、答案、T/F 由組員提供；評分端才讀凍結答案／劇本。 |

正式 registry 尚未配置 live Q5 Agent factory；Q3 LLM→Q1/Q2 的 parse provenance 為 §14-23 未決。本工程試用不宣稱已接通正式模型。

## 兩種方式怎麼比較

- 相同 index／clock／圖／參數／query／selected seed，僅 switch_mode 不同。BACKEND_FLAGS 對應 RULE_ONLY；AGENT_DECISIONS 對應 AGENT_SEQUENTIAL，沒有私加 q2-request.v1 enum。
- kernel 完成並凍結原 response、decisions／links；事件 adapter 不改原 output hash，也不授權額外切鏡。UI 只重播已產生的 SOURCE timeline 和 flags。
- FOUND：觀測支持恢復或核准 kernel 已切到另一鏡頭；附入口觀測 ref，只帶入口那一筆，不把合併 segment 後面的未來觀測當成當時證據。原鏡頭恢復可以 FOUND，但 switch=false。
- LOST：選定起點後，連續無觀測支持超過操作者明給的 `lost_after_us`，保留失聯鏡頭、通知一次；恢復支持後才可開始下一段失聯計時。這不是「確定人不在」，所有候選未必都有完整證據。
- 期限用來源微秒；恰於期限恢復時不先閃 LOST。查詢右端是半開界，不在範圍外發通知。還沒選到起點不發 LOST。
- 沒有正式預設期限。工程範例 600000 us 僅為2秒機械fixture中的測試值，EXPERIMENT_ONLY_NOT_APPROVED；不替代 link_max_gap_us、不改已核准參數。
- 比較呼叫數、取證數、切鏡／LOST 次數、故障兜底及原 trace replay 一致性；沒有人工答案，不計準確率。機械 FakeProvider 的呼叫數不是實際 Ollama token／延遲／品質量測。

## 重現

在具名的多 PR source composition（含上游 #169/#172）中，使用既有 Python：

```sh
df -k "$Q1Q5_OUTPUT_PARENT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/compare_q1q5_event_modes.py" --synthetic \
  --lost-after-us 600000 --output "$Q1Q5_OUTPUT_PARENT/new-run"
```

output 要全新，既有檔不覆寫，產製前後 df-k，低8GiB停止。沒有 Blender、權重下載、模型連線或原始素材讀取。逐情境保留 Agent trace，並用 RecordedProvider 斷線重跑；domain hash、decisions、links 須完全相同。

瀏覽器試用是 `frontend/workbench-v2/event-modes.html`，同目錄提供 generated `comparison.json` 與既有 q-validate／q-time 模組。從 localhost 靜態server 開啟；只發布 web 檔，不把 private trace 根目錄當靜態站台。可以選後端、Agent或並排，切換5個機械情境，播放／重播／拖SOURCE時間。沒有真RGB，兩邊都明示 RGB MISSING。

工程情境：有支持的第一候選、第一候選空但後面有支持、所有候選空、暫失後原鏡頭恢復、provider故障。它們是程式控制測試，不是組員題目或標準答案。

## 未完成與限制

#183 原契約仍不允許空 observation 引用的 NEXT。此版本保留它：機械策略遇空證據合法 RETURN，不偷偷換成能跳過空證據的 Agent；因此可直接看出後端模式與目前 Agent 協議的差異。修法列 §14-26，未核定／實作。事件通知方式與期限列 §14-27。

這是一個可播放的工程比較包，非 live streaming 通知端點或正式 r004 Demo。正式RGB、Agent真模型與人工評分仍待既有#115/#118/#147／契約與模型設定。上游Draft與原kit FAIL未解除前，本任務維持Draft，不可拿SYNTHETIC對比當正式比較結論。
