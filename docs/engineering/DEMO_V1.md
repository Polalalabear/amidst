# 第一版 demo：來源證據、多條路線、可保存的調查

更新：2026-10-14。這是本機合成研究展示；Phase 2 功能工作量仍估約 **50%**。
前五段可作第一版主展示，保存 Agent 結果作有明確限制的加映；不把可操作 demo 當作 05／11 品質驗收通過。
以使用者列出的六段展示操作為分母，目前核心五段5/5可操作；包含Saved Agent加映時為5/6（約83%）在新動態入口完成排演。這是操作就緒比例，不是研究準確率或Phase2完成度。
最新逐段排演與交付狀態見文末及 [demo 收據](../../data/engineering/phase2_repair_0511_20261013/demo_v1_readiness_20261014.json)。

## 約九分鐘的展示腳本

| 時間 | 操作 | 觀眾應理解的重點與限制 |
| --- | --- | --- |
| 0:00–1:00 | 開啟當次 `DEMO_URL`，研究 → Blender Office；兩鏡頭、完整 0–9.8 秒、K=3 | 已有來源 RGB、校正與局部幾何；橙色目標是合成替代資料。Office 的相機名稱沿用 Auditorium，不能由名稱認定房間歸屬。 |
| 1:00–2:30 | 2D 分時牆／3D，播放或拖曳來源時間軸 | RGB 是觀測；地面投影是衍生位置；短橋是推斷；無資料時保持 MISSING，不延伸上一個位置。 |
| 2:30–4:00 | 跨鏡頭多解還原，切三個候選與排序外未關聯基線；查看 XYZ／速度曲線與既有影片 | Office 五個唯一配置中回三解；同證據支持不同關聯假設。分數不是機率，不確認人物身分或真實路線；影片是完整雙鏡頭／K3 的預先物化素材，窄窗不重製影片。 |
| 4:00–5:00 | 可選 Classroom101 走廊負例，再明確切換「局部多鏡頭研究場景」E1 | 走廊有 50 來源影格、0 有效投影，缺失保留；Classroom 只回一個未關聯基線，不湊 K。Office 與 E1 是獨立資料，沒有正在追查同一人物的證明。 |
| 5:00–7:00 | E1 → 人物調查 → 照片與觀測 → DOOR／8–16 秒 → 取得局部人物片段 → 選片段追查 → 建立並保存 TRACE 計畫 → 逐步執行 | 四鏡頭既有合成資料中的局部片段；計畫、工具收據、替代與未知可追查。這段是既有調查能力，不是新多人事件實作。 |
| 7:00–8:00 | 開啟保存案例，取得報告，匯出 HTML | 調查可保存、重新開啟及交付；引用是來源證據，不是身分／行為正確率證書。 |
| 8:00–9:00 | 可選開啟事前完成的 accuracy-v2 → 調查與品質 → DOOR／8–16 秒 Agent 結果 | 自然語言對應公開欄位、引用、UNKNOWN 與分頁。展示保存答案，不現場等待推理；最新模型品質仍未達標，舊結果唯讀且需求完成度 NOT_CHECKED。 |

物理篩選只作限制解說：Office 候選仍全為 **UNKNOWN**，硬排除 **0**。
Office revision20／Classroom revision15 的 35 筆人工差異與兩站既有重跑已保存，38 個有效物理檢查仍 UNKNOWN；Auditorium 尚未開始人工核對。
獨立Phase1正式分支043bed2已完成其受限Case1–3的18項Exit gates與乾淨重現；Case3 ADE改善0%未達30%初始目標、整校幾何仍未認證，詳見[正式報告](../research/PHASE1_FINAL_REPORT.md)。它不替這組Office展示增加物理權限。

缺少核准門孔尺寸／法向、完整走廊／人體域及相機對應，排名變動不能當作已確認路線、可通行或全場無碰撞。這些工作屬獨立人工核對範圍，不能靠 demo 升權。

## 目前依賴與啟動

已有輸出時跳過 build；不可直接覆寫凍結輸出。Blender 畫面展示不需現場執行 Blender 或重新 render，**仍需原 .blend 與已物化 RGB／校正／幾何／PNG／MP4** 通過既有來源綁定。
GitHub 僅發布程式、文件及整理收據；ignored 媒體、模型權重、SQLite／PostgreSQL 狀態沒有隨 clone 提供。新 clone 不是完整可攜 demo 包。

目前 E1／accuracy-v2 保存計畫、案例與報告已使用本機 PostgreSQL；不能保證關掉 PG 仍能讀到這些案例。Saved Agent 入口還需要 PG 與 Ollama 的本機模型清單服務；重新開啟舊回答不產生新的模型 completion，但不等於零服務依賴。部分舊 SQLite 模式可獨立運作，不能代替目前保存資料的依賴核對。

動態新origin不會繼承8016的瀏覽器localStorage recovery token，新的server owner session也不會自動列出舊Agent案例；只指定同一workbench state不足以恢復。Saved Agent加映需在當次DEMO_URL以原credentials完成既有恢復；本輪新入口清單為0，尚未重開舊Agent回答，所以暫跳過加映，不為此新起模型推論。E1 PG保存案例已在新入口成功重開，與Agent私有恢復機制分開。

使用實際工程 checkout 與既有本機 state，明確指定來源 `PYTHONPATH`，避免共用 editable 環境指向另一 checkout。`DEMO_STATE` 指向現行必要 SQLite，`DEMO_CANONICAL_ROOT` 指向原資產 checkout；這些本機路徑不寫入前端。預設讓作業系統分配埠號，也可由環境變數指定：

```sh
export DEMO_REPO="$PWD"
export PYTHONPATH="$DEMO_REPO/src"
: "${DEMO_STATE:?請設定既有工作台 SQLite 的絕對路徑}"
: "${DEMO_CANONICAL_ROOT:?請設定原資產 checkout 的絕對路徑}"
uv run --offline --no-sync python -m amidst.workbench \
  --port "${DEMO_PORT:-0}" --repo "$DEMO_REPO" \
  --canonical-root "$DEMO_CANONICAL_ROOT" --state "$DEMO_STATE"
```

前提是依賴已安裝；展示前不以 `npm ci` 或線上下載作啟動步驟。CLI 的歷史啟動訊息在 `--port 0` 時印出請求值 0，不能把它当成實際網址。另一個終端先核對本次 Python process 的 PID／argv，再取得實際 listener；以下 `DEMO_PID` 必須填該次 PID，不猜埠號、不終止其他 process：

```sh
: "${DEMO_PID:?填入本次 workbench Python process 的 PID}"
export DEMO_PORT="$(lsof -a -p "$DEMO_PID" -iTCP -sTCP:LISTEN -nP -Fn | sed -n 's/^n127\.0\.0\.1://p')"
: "${DEMO_PORT:?找不到該次 workbench listener}"
export DEMO_URL="http://127.0.0.1:${DEMO_PORT}/"
curl --fail "${DEMO_URL}api/bootstrap"
```

`8016` 是既有文件與歷史收據的工作台入口；本輪依使用者要求另起 `--port 0`，實際 URL 只記本機 endpoint 紀錄與當輪回報，不寫死於設定。所有 `/api/` 與媒體繼續用同 origin。

## 測到哪裡，為何尚未達標

| 範圍 | 已驗證／目前結果 | 尚不能宣稱 |
| --- | --- | --- |
| 原 main R1 demo | main `439c8669eae740ed5750eeb1f853c0ddf73ec507`；merge tree 與已測 R1 `7d053543316d13272039402d33eb3c3bcab06ba8` 相同，原 Python3567／owned Node232 收據 | 不是本輪重新跑 main 全套；不含另一對話 `158d74c` 全部 Blender 顯示 checkpoint。 |
| 目前工程 runtime | `b1cf0c406140dd0a38a17456de961839dbf63f9a`；runtime734132…；Python3736 PASS／0 fail/error/skip，Ruff／mypy235 檔 PASS；HTTP68 守門 PASS，23 SCRIPTED、0 真實模型 | fixture／HTTP PASS 不能當本機模型自然語言品質分數。 |
| 11 R2 全題實測 | 40 常規＋8 安全全部執行：常規12/40（中文7/20、英文5/20），接受literal欄位417個錯誤0；4個 DETAIL 完整性誤報。安全邊界8/8，但正確拒絕原因與語言2/8；澄清完成0/8 | 未達常規36/40、各語言18/20及完整性誤報0的門檻；不能說完整品質驗收已通過。 |
| 11 最新 R3 實際 demo | 首次真實呼叫75.660秒、1call／0tools，模型要求不存在的 `query_receipt` 事實欄位，守門拒絕 `AGENT_GOAL_FIELD_UNAVAILABLE`，FAILED已保留 | 舊162.430秒成功屬R2歷史案例，不能當最新版成功；新的48題回放尚未開始。 |
| 11 修正準備 | prompt24916→22069，既有24k上限不放寬；進一步schema／generic read-verb候選已private220 fixtures／獨立peer PASS，仍未套用 | 未套用候選、未取得新真實回答或48題品質PASS，不提前提高進度。 |
| 05 局部追蹤 | 唯一候選開發strict gain未過；固定test `(4,3,7,6)→(3,2,7,6)`，fragmentation仍7>6，缺採樣總數11不變，維持baseline | switches／mixed的局部改善不足證明整體身分品質；不依曝光test再調參，不建立新sealed測試集。 |

11 R2 108 次實際模型呼叫的 P50 58.062秒、P95 110.844秒；這是每次呼叫延遲，不是每個完整調查延遲。
R2 保存 demo 是162.430秒完整調查，現場啟動模型會拖慢九分鐘節奏。舊typed v2／v3結果保留literal來源但唯讀、當前需求完成度 NOT_CHECKED；v4需要新的實際模型及全題驗收。
最新修正使用同一已曝光PUBLIC R2題組時，只能標 `EXPOSED_LOCAL_PUBLIC_REGRESSION_NOT_INDEPENDENT_HOLDOUT`。
詳細原始失敗、驗證及main範圍見 [05／11修正](PHASE2_LOCAL_REPAIR_0511.md)；歷史收據不累加為新的PASS。

## 交付與排演紀錄

固定程式版本：目前工程展示起點 `b1cf0c4`，main穩定R1 `439c866`；Blender與E1／accuracy-v2資料版本及hash沿用各來源manifest，必須在展示時明列場景切換。對應[curated原結果](../../data/engineering/phase2_repair_0511_20261013/)與[來源展示](SOURCE_PRESENTATION_WORKBENCH.md)保留來源綁定。

2026-10-14新動態入口已確認bootstrap六場景、Office雙鏡頭K3、候選／未關聯基線、4.8秒游標與MISSING、2D八張原影格。E1 DOOR／8–16秒TRACE新建、單步、完成19工具／69替代、保存重開與HTML匯出也已實際通過；HTML2166 bytes／UNRESOLVED_PROVISIONAL，含DETAIL／MEDIA預算未解項。Classroom雙鏡頭走廊負例與Agent新origin限制另記；其餘本輪排演結果以demo收據為準，不把歷史browser成功當本輪全部重跑。90秒精華錄影尚未製作，不能宣稱完整展示包已交付。

正式展示前準備保存案例與HTML，核對原影片與來源版本；先走完整一遍，再視需要錄90秒精華。11品質與共享任務尚未完成，必要資料保存／服務退役／finalization工作樹刪除還沒執行。暫緩項目持續暫緩。

## English

The first local demo tells a nine-minute story: source evidence → alternative routes → a saved investigation. Use Blender Office, two cameras, 0–9.8s and K=3; explicitly switch to the independent E1 dataset before TRACE, saved cases and HTML reports. Office candidates remain UNKNOWN with zero hard exclusions. Classroom corridor retains 50 source frames and zero valid projections.

The five core demonstration operations are ready (5/5); including the saved-Agent extra, fresh dynamic-origin rehearsal is5/6, approximately83%. The new origin does not inherit the prior Agent recovery token/owner session and currently lists zero saved investigations, so that extra remains unrehearsed. E1 saved PG cases reopened successfully. Agent quality remains unaccepted. R2 completed all48 but passed12/40 normal questions; safety boundaries passed8/8, clean refusal quality2/8. The current engineering runtime passed3736 Python tests and68 scripted HTTP checks; its first actual model demo failed on an unavailable requested field. A private follow-up candidate and a new complete model replay remain pending. Keep05 baseline and Phase2 effort estimate at50%.

Run the existing checkout with explicit PYTHONPATH, existing state and `--port "${DEMO_PORT:-0}"`; discover the actual listener of the verified Python PID and set DEMO_URL. No new fixed port is introduced. Original assets are required; current PG-backed cases need PostgreSQL and saved Agent setup additionally needs Ollama. GitHub does not include ignored media, weights or databases. The90-second video and complete portable presentation package are not yet delivered. See the dated readiness receipt for the exact fresh rehearsal scope.
