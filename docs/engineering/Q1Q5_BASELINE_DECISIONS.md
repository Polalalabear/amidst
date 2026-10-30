# Baseline 一次驗收：產品契約與核定清單

Refs #200、#144、#145、#183、#189。以下列出可以直接修正的既有行為，以及必須由使用者/獨立審查核定的新語意。這份清單不把提案改寫成已批准，也不修改 #127/#135。

| 項目 | 本輪實際處置 | 正式啟用前的具體決定 |
|---|---|---|
| 同步 Q2 publication race | 已修：`_active` 保留至 bundle 驗證及 response 發布完成；相同請求在窗口內沿原 `Q_SESSION_RUNNING` 拒絕，完成後回快取。沒有新增狀態或guard | Claude 覆核新 API 檔與 barrier focused。原 #189 固定來源/4 strict XFAIL 不回改；它不是新修正的測試結果 |
| Q3→Q2 操作者模式 | #195 已複製結構化 request 套既有 Q5 mode，原 Q3 response/hash不改 | 覆核現有接線，不需要新 enum |
| #145/D69/失敗digest/空journal | 原 domain bytes 與完整 FAIL 已交回獨立 kit owner；沒有刪 D69 欄位、補造 records 或假填 digest | Claude 對齊最終契約；Codex 不改 #127/#135。非初始成功觀測到的digest不能當已觀察證據 |
| #183 空 evidence NEXT | 目前 guard 保留，RULE fallback 可救回但不算 LLM 成功 | A：只讓已 fetch 且精確綁定當前 candidate/snapshot 的 NEXT 引用 evidence hash，升版 envelope；SWITCH仍須原 entry observation/guard。B：維持非空 observation 引用，無可引用證據時顯式轉整段 RULE fallback，新增對應原因。建議A，風險為 wire/consumer/kit 協同升版與輸出成本；B犧牲該輪 Agent 後續決策。兩案均不得把 UNKNOWN 當不存在 |
| Q3 lineage（§14-23） | staged telemetry 明列 Q3 attempted/used/fallback，原下游 domain bytes 保留；真LLM下游標未決 | 依 #144 §14-23 最終選項決定跨階段旗標/hash兼容性。不能把Q3成功解析與Q5決策採用混成同一指標 |
| Q5 SWITCHING / stop | 不自行新增 journal 或 stop route；現有 player pause 不能當 backend 停止 | 按 #189 釐清 SWITCHING journal與controller狀態的關係；stop需明確合作取消邊界、是否寫終止回應、client取消後server仍可能執行及未完成recording處理。這些尚未有批准wire，不以未核准endpoint冒稱完成 |
| Qwen3 原預算 | 明示 2000ms/5000ms 的 Q5與 Q3 proposed2000，實機 timeout 如實記錄，完整 RULE 接手 | 原硬體/完整wire尚未證明預算內採用；若需compact decision/server展開或預先備證據單步決策，沿 #144 已列選項獨立核定。不能私加15秒或以機械fixture當模型成功 |
| 正式 LOST 期限 | 工程事件分析用明示 synthetic lost_after_us；正式值仍未定 | 不把link_max_gap當正式接回期限，正式事件指標需先核定定義/值 |
| Q3最小題組 | #199八題候選/順序/hash與空白獨立審核表已交，未送受測Qwen | 一次核對KEEP/REVISE/EXCLUDE、精確expected、合法context，另凍結selection與independent expected收據；AI草稿未審不能入正式分母 |
| r004產製 | #197新pinned registration入口與設定已交；原審查包不改 | 回收yyin CSV+問題/不確定/未完成清單+完整folder/ZIP；另需Claude圖/ROI及必要HSV核定。再凍結run/camera/clock/設定→正式RGB→index。D70既有渲染授權不重問 |

可展示的是工程合成流程與明示缺失/未知，不是真模型追蹤品質或正式 baseline。驗收時可逐項接受工程交付、選定契約方案與核定資料範圍；未決部分保留 blocker，不能因為其他項通過而一起升權。
