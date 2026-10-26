# 組員工作指南（資料夾流程，不用 Git）

> 日期：2026-10-25（D78 之後的現況）。給人類組員（yyin）。**你不需要 Git、GitHub 帳號、Python、終端機或 coding agent**：使用者交給你一個資料夾或 ZIP，你用瀏覽器填表，把存好的檔案放進指定資料夾，整包交回。流程依據是 [#147](https://github.com/Polalalabear/amidst/issues/147)（組員沒有 repo 權限）、D70、D71、D75、D76。
> 本文是快照；即時狀態看 [任務板 #93](https://github.com/Polalalabear/amidst/issues/93) 與 [進度導覽](../operations/Q1Q5_PROGRESS.md)。找不到依據的寫 `UNKNOWN`。本文沒有執行任何程式、渲染或推論。
> 修訂紀錄：2026-10-25 依 Codex 對 PR #83 的審查（[comment 6309402033](https://github.com/Polalalabear/amidst/pull/83#issuecomment-6309402033)）改寫。舊的 Git／分支／PR／JSONL 流程已移到 §8 當歷史附註，組員不再需要。

## 0. 三分鐘版

- **專案**：Q1 依條件找相機、Q2 在影片中找人、Q3 理解使用者措辭、Q4 判斷 2D 畫面是否含目標、Q5 目標離開時判斷是否切鏡。全貌見 [Q1Q5_COLLABORATION_INDEX](Q1Q5_COLLABORATION_INDEX.md)、[SYSTEM_OVERVIEW](SYSTEM_OVERVIEW.md)。
- **你做兩種工作**（§3，輸入、輸出、防偏誤規則不同，不要混）：
  1. **獨立出題**：Q1／Q3 自己寫使用者會說的話與預期結果。不看系統輸出。
  2. **審系統聲明**：Q4 看一張畫面和系統的說法，判 T／F／不確定。
- **你不做**：不寫程式、不開 PR、不評分、不處理「追得好不好」（D71）、不看 Ground Truth（GT）。評分程式、schema 由 Codex 寫（D70）；你的 CSV 由 Claude 轉成評分格式（D75）。
- **現況**（細節 §4）：
  - 你 2026-10-24 交回的 r004 前置審查 v2（132 項）已收到，全部有效；協調者另打了一包 3 題的澄清包（T-1），LOCAL，待使用者交給你。
  - Q1／Q3 出題（T-2）的出題指南修正已由 [PR #221](https://github.com/Polalalabear/amidst/pull/221) 合併進 `codex/q1q5-staging`（merge `e52ace3`），尚未進 `mainline/q1q5`；Q4 正式 T／F（T-3）在等正式輸出。這兩項**現在還不能開始**。
  - `main` 不動（D72）；任何一份包的結果都不是正式驗收。

## 1. 你怎麼收件、做、交回

1. **收到**一個資料夾或 ZIP（由使用者交給你，不經 GitHub）。完整解壓，不要只開裡面的一個檔案。
2. **開說明檔**：`README.txt`（或 `README.md`），三段：工作內容／要提交項目／操作（格式見 §2）。
3. **用瀏覽器開 `START_HERE.html`**（離線，不需要網路）。填「審查者」「日期」，逐題看圖或讀情境，填答案與理由。
4. **匯出**：按頁面的「匯出回覆 CSV」。頁面不會自動儲存，**關頁前一定要先匯出**。要中途停，下次用「匯入 CSV 接續填寫」選你上次匯出的檔。
5. **存成指定的 RETURN 檔**：把下載的 CSV 放進包內 `RETURN/`，檔名照說明檔，例如 `RETURN/審查表_yyin_YYYY-MM-DD.csv`。沒填完的列保留，檔名會自動帶 `_INCOMPLETE`；**不要刪列**。
6. **整包交回**使用者（完整資料夾或 ZIP，CSV 已放進 `RETURN/`），附一段交件訊息：做了哪些類別、沒做完的項目和原因、有疑問的地方。
7. 使用者再交給 Claude 匯入；你不會被要求做 Git、JSON 或 schema。

注意：

- 只改回覆欄（`decision`、`reason`、`reviewer`、`date`，頁面會處理）。不要改 `templates/`、`DATA.json`、`data.js`、圖片、`provenance/`、`tools/`、`MANIFEST.json`。包被改過，收件端的核對（§7）會拒收。
- `T`＝支持這句敘述、`F`＝反駁、`不確定`＝證據不足。`F` 和 `不確定` 一定要寫理由；不要猜。
- 圖片與系統說法**不要上傳到任何外部 AI 或雲端服務**：第一版不用外部 API（D64），送外部畫面的授權範圍還沒決定（[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) §5）。標準答案要來自你自己的判斷（D70，保持評估獨立）。
- 包內所有圖與材料都標 `PROPOSED`／`PILOT` 時，**不自動核准任何東西**，也不是正式評估。
- 手上如果有 GT、`.blend`、private 檔、劇本、路線、人物設定：**不要打開**，通知使用者（§5）。

## 2. 每份組員包的固定格式（D76、CX-9）

之後交給你的任何工作都是這個格式。範例是 **r004 前置審查包 v2**（LOCAL `$AMIDST_ARTIFACTS/r004-prereview-team-v2_20261024/`，資料夾約 10.4 MB（`du` 10,700 KiB）；132 項，欄位與固定材料由 `MANIFEST.json` 鎖定，`MANIFEST.json` SHA-256 `531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4`，以 2026-10-25 對 LOCAL 檔計算）。

| 項目 | 內容 | v2 包裡的檔案 |
| --- | --- | --- |
| **說明檔**（三段） | ① 工作內容（做什麼、對象是誰）② 要提交項目（RETURN 檔、整包、交件訊息）③ 操作（逐步，末尾寫明「只改哪些欄、不要改什麼」）；D76 另要求寫明「不要改」 | `README.txt` |
| **填表頁**（離線 HTML） | 瀏覽器開，不用安裝；固定材料唯讀；匯出／匯入 CSV | `START_HERE.html`、`app.js`、`data.js`、`style.css`、`images/` |
| **指定的 RETURN 檔** | 說明檔指定檔名；一律放 `RETURN/`；例如 `RETURN/審查表_yyin_YYYY-MM-DD.csv`；未完成帶 `_INCOMPLETE`；列數固定，不得刪列 | `RETURN/`、`templates/審查表.csv`（空白範本） |
| **核對工具** | `tools/verify_pack.py`（核對包與回覆 CSV）；`MANIFEST.json` 逐檔 SHA-256；說明檔或交付訊息附 MANIFEST 的 SHA-256 | `MANIFEST.json`、`tools/`（v2 包的核對工具叫 `verify_bundle.py`，之後的包統一叫 `verify_pack.py`） |
| **依據與資料** | 每一題的來源與備註，頁面上可展開「查看項目依據與資料」 | `provenance/`、`DATA.json` |
| **不是什麼** | 包本身不核准任何東西，不是正式評估 | `BASELINE_READINESS.md`（v2 包另附，說明審查期間可並行的工作） |

3 題澄清包（T-1，LOCAL `$AMIDST_ARTIFACTS/team-handoff-yyin-20261025.zip`）是同一格式：ZIP 2,936,162 bytes（約 2.8 MB），ZIP SHA-256 `c6ac1cee61676614263c592e45a5c5a8fde3ca97bba922dbe5fdc7008a2339e7`，`MANIFEST.json` SHA-256 `d84bfbb6bdc6685e6abcc29603377535db259ab4d4b98c79a87c0a8ec3b73657`（取自 [COORDINATOR_HANDOFF_20261025](COORDINATOR_HANDOFF_20261025.md) §7）；回交檔 `RETURN/審查表_yyin_YYYY-MM-DD.csv`，3 列都要保留。

Q1／Q3 出題包與 Q4 正式 T／F 包**尚未產生**；產生時會附同樣的三段說明檔、`RETURN/` 與核對工具，並把包的 MANIFEST SHA-256 貼在 #93。

## 3. 兩種組員工作（輸入、輸出、防偏誤規則分開）

| | **A. 獨立 Q1／Q3 標註（出題）** | **B. Q4 審系統聲明（T／F）** |
| --- | --- | --- |
| 目的 | 產生**獨立的標準答案**：系統做不做得到，由你先寫下什麼算對（D70、D71 第 4 點） | 判斷**系統對這一格說的話**是不是真的（D71 第 4 點）；用來估偵測與顏色判斷的錯誤 |
| 你看到什麼 | 出題指南：可用的詞（類別、顏色、鏡頭與區域的中文說法）、每個 run 的時間範圍、找得到／找不到／不支援／超出時間／反問的情況、r004 場景裡有哪幾**種**東西（[#146](https://github.com/Polalalabear/amidst/issues/146)，指南檔在 [PR #149](https://github.com/Polalalabear/amidst/pull/149)，`docs/evaluation/Q1Q3_QUESTION_AUTHORING_GUIDE.md`，目前只在 staging，且需修正） | 一張抽樣畫面（檔名是樣本編號）＋系統對這一格的說法，例如「這格有紅衣人」「這格有車」「這格沒有人」 |
| 你**不看** | 系統輸出（偵測索引、Q3 解析器輸出、Q1 結果）、Codex 準備的候選題（#199 不當題目來源，D76）、逐時段「誰在哪台」、劇本、路線、GT | 路線、人物設定、GT、劇本；追得好不好（Q2／Q5 由系統輸出凍結後直接和劇本自動比對，D71，與你無關） |
| 你做什麼 | 寫使用者**會說的話**，並寫預期結果（找得到／找不到／不支援／超出時間／反問）；Q3 最小題組 **8 題由你自己出**（D76）；所有題目標 `SYNTHETIC`、不含真實人名與個資 | 對每一格判 `T`／`F`／`不確定`；`F`、`不確定` 必填理由；抽樣**同時包含系統說「有」與「沒有」的畫面**（D71），才抓得到漏抓 |
| 交回 | `RETURN/` 內說明檔指定的情境 CSV（欄位大致為：編號、使用者會說的話、想找什麼、顏色、開始與結束時間、鏡頭或區域、系統該不該反問、預期結果、備註；以包內 `templates/` 為準，#147 的提案欄位） | `RETURN/審查表_yyin_YYYY-MM-DD.csv`（欄位大致為：樣本編號、圖檔、系統說法、答案 T／F／不確定、備註；以包內 `templates/` 為準） |
| 誰轉換 | **Claude 直接把你的 CSV 轉成評分格式**（JSONL），Codex 不參與也不預填（D75 第 2 點）；轉換紀錄附你的 CSV 的 SHA-256 | Claude 匯入（CL-7）；組員沒填或格式錯的列標 `INVALID` 並列出，不補、不猜 |
| 防偏誤規則 | ① 先寫題目與答案，**之後**才可能看到系統輸出；② 不為了讓系統過關而出題；③ 不改題目去配合系統結果；④ 你的答案不回填索引、參數、排序、圖或 prompt | ① **建議盲測，不預填**答案欄；② 不附系統信心值或抽樣組別比例給你；③ 不要因為前面都是 T 就跟著填 T（r004 v2 的 70 題 HSV 全填 T，協調者建議正式 Q4 改成盲測）；④ 看不出來就填 `不確定` 並寫理由；⑤ 抽樣與樣本↔run／camera／frame 的對應只放 `MANIFEST.json`，不放進你的 CSV |
| 試填（PILOT） | A／B1 試標只當流程與判定規則的試稿（D68），標 `PILOT`，**不進任何評估分母**、索引、參數、排序、圖或 prompt | 同左；v0-pilot 的 24 張畫面試填與 r004 包的 70 題 HSV T／F 重疊，已從澄清包拿掉（見 [COORDINATOR_HANDOFF_20261025](COORDINATOR_HANDOFF_20261025.md) §7） |
| 對應的 issue | [#89](https://github.com/Polalalabear/amidst/issues/89)（Q3）、[#138](https://github.com/Polalalabear/amidst/issues/138)（Q1） | [#128](https://github.com/Polalalabear/amidst/issues/128)（Q4） |

通用原則（A、B 都適用）：

- 推論端（偵測索引、兩層圖、Agent／LLM、參數）**不讀**你回交的標註，也不讀劇本。你的結果只用在凍結後的評估。
- 你的答案不是通過門檻。門檻由使用者決定；你不用也不應該依看過的結果改答案。
- **Q5 沒有組員工作**：系統輸出凍結後，Q5 直接和劇本比對（D71）；決策窗寬由 Claude 提案、使用者核定（D75 第 3 點）。[#129](https://github.com/Polalalabear/amidst/issues/129) 的組員欄位是否已更新：以 #93 為準，本文不排工作。
- 瀏覽器驗收（[#130](https://github.com/Polalalabear/amidst/issues/130)）與「交接試跑」（D68）需要可攜測試包（CX-10，Codex，**尚未交付**，見 [Q1Q5_LOCAL_TEST_SETUP](../operations/Q1Q5_LOCAL_TEST_SETUP.md) §1）。在那之前不排。

## 4. 關卡（checkpoint）與你的工作卡在哪

### 4.1 關卡一覽（2026-10-25）

| 關卡 | 內容 | 現況 | 依據 |
| --- | --- | --- | --- |
| G1、G2、G6、G7、G75 | 計畫與契約核准、契約 SHA、參數初值、工作台設計、底座合併 | 成立 | [COLLABORATION_INDEX §1.2](Q1Q5_COLLABORATION_INDEX.md) |
| G3 | Q1–Q5 Agent 有界例外 | **成立**：PR [#125](https://github.com/Polalalabear/amidst/pull/125) 以 merge `f915fb0` 合進 `mainline/q1q5` | D67 |
| 契約定版 | 契約修正 R1–R8 並寫入 D73（CX-1，[#144](https://github.com/Polalalabear/amidst/issues/144)） | 等 Codex 寫進條文、Claude 複核；§14 選項已全部決定（D73） | D71 第 1 點、D73 |
| **G4** | r004 靜態圖 v3 修完（R01–R08 加 10 項施工）→ **Claude 複核** → **使用者一次核定**；通過後才凍結圖與出口區域、才產生正式事件 run | **未成立**；v2 不能照現狀凍結，等 Codex 圖 v3（CX-3） | D74、D77 |
| 渲染與正式索引 | A4／B4 事件 run（#115）與正式索引（#118）已由 D70 授權，但 D74 規定在 G4 凍結**之後**才做 | 等 G4。每次產製前後記 `df -k`，可用空間低於 8 GiB 立刻停；12 GiB 開始門檻由使用者判斷 | D70、D74 |
| **P1 工程預驗收** | 工程動態場景（8 秒、20 fps）驗操作流程與畫面跟隨（AC1–AC8）；**不是正式成績** | 等 CX-4 整合分支、CX-5 預驗收版、Claude 預走查 | D76、[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) §2 |
| **P2 正式 baseline 驗收** | r004 A4／B4 正式事件與正式索引；RULE_ONLY 與 AGENT_SEQUENTIAL 兩模式、錄製、輸出凍結、評分 | 等 G4 → CX-7 → CX-8 → CL-5 | D76、驗收計畫 §2–§4 |
| `main` | 更新與否 | **不動**；等正式 baseline 跑通且 #127 測試包對最終契約通過後，另問使用者 | D72 |

staging 與主線（D70、D75）：Codex 的工作先合進 `codex/q1q5-staging`（Codex 自審、自己用 merge commit 合進 staging，條件是 #127 測試包與 focused 測試通過）；Claude 再審 staging、分批合進 `mainline/q1q5`。第 1 批已在 2026-10-25 合進主線（[#213](https://github.com/Polalalabear/amidst/pull/213)），staging 其餘 PR 等修正後分批合。**staging 合併不是正式驗收**。

### 4.2 你的工作各卡在哪

| 編號 | 工作 | 狀態 | 卡在哪個關卡／前提 | 完成後 |
| --- | --- | --- | --- | --- |
| **T-1** | r004 的 3 個澄清問題（CAM_BRANCH 備註、CAM_WIDE 邊緣、W1→EXT_CAR 短暫消失） | 包已備好（LOCAL）；待使用者交給你 | 無；不用改原本的審查表 | 回覆由 Claude 匯入，併入圖 v3 的複核（CL-3），影響 G4 前的複核，不等於核准 |
| **T-2** | Q1／Q3 出題，含 Q3 最小題組 8 題（工作 A） | **不能開始** | 出題指南修正已由 [PR #221](https://github.com/Polalalabear/amidst/pull/221) 合併進 `codex/q1q5-staging`（merge `e52ace3`），尚待 CX-2 併入 `mainline/q1q5`；之後 Claude 另出包。與 G4、渲染**無關**，可在圖 v3 之前做 | Claude 轉成評分格式（D75）；輸出凍結後由 CL-5 評分 |
| **T-3** | Q4 正式 T／F（工作 B） | **不能開始** | 等 CX-8 的**正式輸出**（G4 → CX-7 渲染與索引 → CX-8）；工程場景（P1）與 PILOT 不當正式分母 | Claude 匯入（CL-7）；輸出凍結後評估 |

「不能開始」的意思：現在沒有可交給你的包。不要自己找檔案或自己做替代版本；包準備好時使用者會交給你。

## 5. 紅線、資料與磁碟界線

1. **你拿不到、也不該看 GT**：`private_evaluation/`、`production/`、`review_only/`、`persons.sim.json`、`gt/`、mask、depth、renderer 的 visibility／trajectory、`acceptance/d47_screening.json`、r004 的人物設定（衣色、路線、速度）、事件腳本與 `event_*.validation.json`。GT 只在輸出凍結、預測 hash 驗證後供評估端使用（D1、D26）。包裡不放這些。意外看到：**不要打開**，通知使用者。
2. **原始產物只放 LOCAL `$AMIDST_ARTIFACTS`**（本機 `~/amidst-artifacts`）：RGB、錄製、權重、資料庫、人工回交（你交回的 CSV）都不進 repo。文件只寫**相對於 `$AMIDST_ARTIFACTS` 的路徑、大小、檔數與 SHA-256**（[AGENTS.md「Handoff documents go on GitHub」](../../AGENTS.md)）；不寫 `/Users/…` 之類的絕對路徑。
3. **不改原始資產**：不修改、覆寫、複製、渲染任何 `.blend`、影片、資料集、校正檔。你拿到的包內檔案一律唯讀，只填回覆欄。
4. **磁碟**：產製 RGB、索引、錄製的人（Codex、Claude）每次前後記 `df -k`，可用空間低於 8 GiB 立刻停止（D70、D41）。你的包約數 MB 到十幾 MB，不受影響；請別在可用空間很少的電腦上解壓大型包，空間不足時告訴使用者。
5. **身分一律 `UNCONFIRMED`**：「系統說有紅衣人」不是「確認是同一個人」。T／F 只判斷**這一格的畫面**支不支持這句話。「沒偵測」不等於「已離開」或「不存在」。
6. **缺資料不補**：包缺檔、`MANIFEST` 不符、版本不符時停下來告訴使用者，不要自己修。
7. **不要自己定數字**：參數與門檻由使用者決定（D65）；你只回答 T／F 或寫題目。
8. **不接外部 API、不把畫面送外部服務**（D64，§1）。

## 6. 遇到問題找誰

你沒有 repo 權限，所有問題寫進**交件訊息**或直接告訴使用者，由使用者轉給對的人：

| 問題 | 轉給 |
| --- | --- |
| 題目怎麼寫、欄位怎麼填、這格該怎麼判、包的格式 | Claude（任務定義、評估端、組員包） |
| 圖片、畫面、系統行為、為什麼系統這樣說 | Codex（後端、索引、r004 資料） |
| 授權、門檻、磁碟、是否核准、`main` | 使用者 |

## 7. 給收件端（使用者、Claude、Codex）

交給組員之前、收回之後都要核對；組員不需要做這一節。

1. **交給組員前**：包放 LOCAL `$AMIDST_ARTIFACTS/<包名>/`；說明檔三段齊全且寫明 RETURN 檔名；不含 GT、劇本、路線、人物設定、`/Users/…` 路徑；MANIFEST 逐檔 SHA-256；把包的大小、檔數與 MANIFEST SHA-256 貼在 #93。LOCAL 的包本身不進 repo；格式說明在本文 §2。核對工具與產生器的原始碼是否已在 GitHub：`UNKNOWN`（AGENTS.md 規定 LOCAL-only 的交接文件要上傳，Codex 的 CX-4／CX-10 負責）。
2. **收回後**核對：
   ```bash
   python3 -I tools/verify_pack.py --manifest-sha256 <MANIFEST.json 的 SHA-256> [--returned-csv RETURN/審查表_yyin_YYYY-MM-DD.csv]
   ```
   固定材料與 `MANIFEST.json` 被改、列數不符、回覆檔名不符，一律整包拒收並請使用者通知組員；不補、不猜。
3. **登錄**：回收檔的 SHA-256 登錄在 `docs/evaluation/TEAM_REVIEW_PACK_REGISTRY.md`（[#147](https://github.com/Polalalabear/amidst/issues/147) 指定，目前只在 staging）。回收檔本身留 LOCAL。
4. **轉換**：Q1／Q3 CSV 由 Claude 直接轉成評分格式（D75），紀錄附來源 CSV 的 SHA-256；Codex 的 #147／#151 回收匯入器（在 staging）要不要用：`UNKNOWN`，以 #93 的 CX-2／CL-7 為準。Q4 T／F 由 Claude 匯入（CL-7）。
5. **GT 隔離**：回收結果只供凍結後的評估；推論端不讀回收標註與劇本。

## 8. 歷史附註：舊的 Git／PR 流程（組員不做）

2026-10-20 的舊版本文（commit `bda073d`）要求組員 clone repo、認領 issue、開 `team/<名字>/<任務>` 分支、寫 JSONL 與評分器、開 Draft PR。這已被取代，**組員不要照做**：

- #147 明定組員沒有 repo 權限，只填文字情境 CSV 與畫面 T／F；
- D70 把評分程式、schema、SYNTHETIC 情境骨架交給 Codex，題目、標準答案與 RGB 標註由組員人工做；
- D75 由 Claude 轉換人工答案。

仍有效的只有 `AGENTS.md` 保留的分支前綴 `team/<name>/<task>`：留給**未來**有 repo 權限的組員，現在沒有人使用，也不在你的流程裡。#89、#138、#128、#129、#130 的 issue 內文可能還寫著分支、PR、JSON 與舊的契約 SHA；衝突時以本文、D70、#147 為準。舊版的 Drive safe 資料包（r003 的 A／B1，`safe_bundle/` 加 RGB）、`uv sync`、契約 SHA-256 核對、測試包（#127）操作，現在都不是組員工作；需要重現這些的人看 [Q1Q5_LOCAL_TEST_SETUP](../operations/Q1Q5_LOCAL_TEST_SETUP.md)，或用 `git show bda073d:docs/agents/TEAM_ONBOARDING.md` 讀舊文。

## 9. 想知道更多時去哪裡

| 想知道 | 去哪裡 |
| --- | --- |
| 這件事誰決定的、還算不算數 | [DECISION_INDEX](DECISION_INDEX.md)（D1–D78）→ 原始留言 |
| 系統由哪些層組成、現在做到哪 | [SYSTEM_OVERVIEW](SYSTEM_OVERVIEW.md)；即時狀態看 [進度導覽](../operations/Q1Q5_PROGRESS.md) |
| 各 Q 怎樣算完成、驗收標準 AC1–AC8、Codex／Claude／組員分工 | [Q1Q5_COLLABORATION_INDEX](Q1Q5_COLLABORATION_INDEX.md)、[Q1Q5_BASELINE_ACCEPTANCE_PLAN](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) |
| 最新交接 | [COORDINATOR_HANDOFF_20261025](COORDINATOR_HANDOFF_20261025.md) |
| 規則（GT 隔離、來源資產、Git、實際產出範本） | [`AGENTS.md`](../../AGENTS.md)、[`docs/DEVELOPMENT_RULES.md`](../DEVELOPMENT_RULES.md) |
