# 審查期間五項closeout（2026-10-25）

Refs #194、#145、#117；base #212。五項授權的工程收尾已完成，各項分開commit並一般push。**正式r004 baseline仍BLOCKED**；這份成果不提供人工核定或runtime authority。

[機器可讀成果](../history/Q1Q5_REVIEW_CLOSEOUT_20261025.json)保留精確數值、來源hash與限制；工具在 [closeout_q1q5_review.py](../../scripts/closeout_q1q5_review.py)。原始圖、回覆、錄製與完整報告保持LOCAL，單一LOCAL README提供全部驗收入口和精確重現命令。

| 工作 | 實際成果 |
| --- | --- |
| #145 | 原樣重驗176錄製，與Claude kit 807b587結果一致；44份Q1新版本補原runtime詞表，消除88個缺context。產品不需依舊kit誤改。 |
| Qwen3 | 量化兩輪18次呼叫，Q3 12／Q5 6，全數在2000ms provider預算逾時；逐次數據、資源缺口與唯讀HTTP／服務日誌證據保留。未新增生成呼叫。 |
| 回收補件 | 新版本80/80固定檔通過、132/132 VALID；補缺模板，CSV原bytes不變，附問題摘要、匯入與交付hash收據。 |
| ROI對照 | 8台／8入口／12出口的SVG多邊形與來源ID逐一對上；22條轉移引用完整解析，原座標不改、仍PROPOSED。 |
| Q3填答準備 | 原8題／8類／原CSV不改；原公共文字只含id/text，review-only材料隔離。context／clock等5組缺件明列，未產正式expected。 |

## #145 完整重驗與context補件

kit固定 `807b587aa8f13da68d186933ad9c7969ffd92d3c`，288個同commit來源檔逐hash固定。沒有改#127/#135/#189、沒有--only；兩輪各176錄製，程序硬拒網路、連線嘗試0。

| 包 | 原樣新版kit PASS／FAIL／缺context | 另版補context PASS／FAIL／缺context |
| --- | --- | --- |
| dynamic（8錄製） | 1521／0／4 | 1531／0／0 |
| linked（8錄製） | 645／0／4 | 655／0／0 |
| runner（160錄製） | 13143／6／80 | 13343／6／0 |

44份Q1錄製的詞表取原runtime或原fixture函數，核對class-map及回應supported引用後另版附檔；原錄製不變。格式仍是kit暫定輸入，不代表§14詞表格式已核定。6個FAIL全是失敗呼叫`model_digest=null`，待§14第20項裁定，不偽造digest、不改產品。沒有把skip或待裁定項當PASS。

## Qwen3逾時診斷

| 階段 | 呼叫／逾時 | provider延遲範圍ms | median ms | p95最近秩ms |
| --- | --- | --- | --- | --- |
| Q3 | 12／12 | 2001.840–2027.825 | 2003.212 | 2027.825 |
| Q5 | 6／6 | 2001.951–2013.333 | 2002.472 | 2013.333 |

每call原2000ms、Q5總5000ms均不改，LLM_used=0。原服務同時間窗有18次POST chat（499一筆／500十七筆）、17個取消紀錄與task processing；沒有request ID逐筆綁定，因此只當時間窗佐證。當前唯讀version/tags/ps為21.746／19.114／0.523ms，目錄中有指定模型、ps未列載入模型，未送生成請求。

可確認呼叫在完整provider回應前達deadline。載入／排隊／生成分段未記錄，保持UNKNOWN，不能斷言只由冷啟動造成；原runner sampler無樣本是監測缺口，不證明模型沒跑。後續若加HTTP階段計時與runner識別，須維持原預算；prompt/output變體另版診斷，不混入正式比較。

## 回收補件、ROI與Q3

新版補件的80固定檔與原manifest一致，132回覆CSV SHA-256仍為`05200de169cfda4ee491e32160977070bc0bbeba3cc93b2cd74c139b23ecd7db`；交回原件仍缺模板但沒有被修改。輸出的IMPORT_RECEIPT與ISSUES不授予核定。

W1／W2圖中X1各對應該台`:EXIT_V2:E_PORTAL_R101`，X2對應`:EXIT_V2:E_VEST_CORR`，X3對應`:EXIT_V2:E_W_CORNER`。E1分別是該台`:ENTRY_V2`。所有20個polygon以0.00051px容差核對SVG三位小數與JSON原座標；完整ROI／轉移／來源圖hash在LOCAL RESULT與ROI_MAP。這不判定應如何移動或加寬，仍交獨立審查。

Q3來源固定#199 `6657fa91cd4af53c0fe225da8e502e88ef6795a4`。新填答包原bytes複製PUBLIC/questions.jsonl與REVIEW_ONLY/REVIEW.csv，另附原guide/freeze、逐題context需求與推論allowlist。沒有轉換CSV欄位／編碼；已重驗八列解析與hash。原靜態catalog沒有run bindings，正式run/time/clock/catalog/核定／獨立expected仍待補；沒有expected.jsonl，formal_rows=0、accuracy=null。缺scope時不猜答案；修訂或排除須另版。

## 驗證、重現與剩餘前置

最終本task focused 12 PASS，兩個Python任務檔Ruff PASS，scoped diff check PASS。每項早期測試數分列收據，不相加冒充獨立案例。無新模型生成、render、browser、正式評分或全suite；初始化的缺依賴嘗試與完成報告分開保留。現有venv只讀使用，不安裝／同步依賴、不改共享服務。

CLI：`uv run --no-project --offline --no-cache --python <existing-python> python scripts/closeout_q1q5_review.py <command> --input <pinned-input.json> --input-sha256 <sha> --output <new-local-dir>`。

commands為`conformance`、`context`、`timeouts`、`supplement`、`roi-map`、`q3-packet`；完整每次argv、輸入／kit／來源pins在LOCAL README。工具完成不等於conformance或正式核定PASS，須讀RESULT內各FAIL／UNKNOWN／PENDING。輸出要求canonical新目錄、拒覆寫、低8GiB停止。

canonical HEAD/index/2026個既有檔保留，不建worktree／reset／rebase／force-push／merge。原人審與歷史驗收JSON不改；GT／actor／事件腳本不進本工具或推論。原#145結果已由本次新版kit重驗補充，#145本身不解除。

仍需Claude獨立圖／ROI、yyin意見處置、適用G4／HSV owner核定、正式Q3答案與scope、剩餘契約裁定與設定凍結。既有D70授權不重問，正式RGB／索引／baseline未啟動。
