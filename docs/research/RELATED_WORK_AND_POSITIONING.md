# 相關工作與定位

- 日期：2026-11-01。基準：`origin/mainline/q1q5` @ `0d78599`。
- 性質：研究文件。**本文不新增規範、不改契約、不改決策**。本系統的敘述只轉述 [Q1–Q5 產品規格](../specs/Q1Q5_PRODUCT_SPEC.md)、契約與 [#93](https://github.com/Polalalabear/amidst/issues/93) 的決策。兩者不一致時，以原始來源為準。
- 查證方式：每筆外部來源都在 2026-11-01 用網路搜尋找到出處頁（arXiv、CVF Open Access、出版社、官方文件或 ML Anthology）。§9 列出每筆的查證狀態。找不到或沒有核對到的欄位寫 `UNKNOWN`。
- 不引用 GT、渲染資料或任何本機媒體。

## 0. 摘要

主流的多鏡頭人物追蹤有兩條路線：

1. **MTMC 管線**：先做單鏡頭追蹤，再抽 ReID 外觀特徵，最後做跨鏡頭關聯。AI City Challenge 是代表。
2. **多視角 3D 追蹤**：鏡頭要校正、視野要重疊，把腳點投到共同地面再融合。NVIDIA DeepStream MV3DT 是代表。

兩條路線的目標都是**全域身分**，也都需要 tracker、ReID 或校正。

Amidst 解的是另一個問題：

- 鏡頭**未校正**，而且**多半不重疊**。
- 系統不確認身分（`identity_verdict` 一律 `UNCONFIRMED`）。
- 只用偵測結果、HSV 顏色與人工核准的鏡頭圖（出口、相鄰轉移），判斷目標離開鏡頭後**該不該切鏡、切到哪台**（Q5）。
- 盲區裡沒有觀測的時段照實標 `MISSING`／`UNKNOWN`，不補軌跡。
- 結果能用預錄回放重現。

最接近的學術脈絡是 2000 年代的**不重疊鏡頭拓撲與 camera link model**（出口—入口關聯、轉移時間分布）。Amidst 的鏡頭圖是人工核准的拓撲，不是從資料學出來的。

## 1. 本系統的事實（定位的比較基準）

| 面向 | Amidst 第一版 | 來源 |
| --- | --- | --- |
| 偵測 | RT-DETR 離線建索引，加 HSV 顏色訊號；查詢時不補推論 | 規格 §2；契約 §4；D63、D64 |
| 追蹤 | 同鏡頭只用 IoU／框中心連接（不是 tracker）；不用 ByteTrack、OSNet、ReID | 規格 §1.3（契約 §1） |
| 身分 | 跨鏡頭只是「條件相符的候選串接」，`identity_verdict` 一律 `UNCONFIRMED` | 規格 §1.2（契約 §1；D63 (d)） |
| 鏡頭 | 未校正的 3D 外參不進推論；鏡頭多半不重疊；重疊接手延到第二版（D77、D90） | 規格 §1.3 |
| 空間知識 | 兩層圖（Region Connectivity、Camera Transition），人工核准後凍結；只表示「依配置可能連通」，不認證通行 | 規格 §1.2、§2；D68、D74 |
| 候選排序 | 決定性：`relation_tier → overlap_area_m2_desc → camera_id`（D28 原鍵）。偵測數、顏色與 LLM 都不進排序 | 契約 §5.4；D28、D64 |
| Q5 | `RULE_ONLY` 狀態機，或 `AGENT_SEQUENTIAL`（Agent 只在合法 top-k 內依序取證，超過上限由規則兜底） | 規格 §2、§4.3；D64、D71、D73 |
| Q3 | 規則語法是 baseline；本機 Ollama 的 Qwen 解析成結構化查詢 | 規格 §1.2、§4.3；D86、D92 |
| 外部 API | 第一版不串外部模型。D107 只對俯視圖示意開「OpenAI 推測」的限定例外，不進評分與判斷 | 契約 §1；D107-1 |
| 盲區 | 沒有觀測就標 `MISSING`／`UNKNOWN`；物理預測只用偵測、鏡頭圖拓撲與出口 | 契約 §1；D107-1 |
| 可重現 | 版本化 JSON／JSONL＋hash；recorded replay 不連模型也能重播 | 規格 §2、§4.3 |

**D28 的範圍。** 依契約 §5.4，D28 本身是決定性排序鍵的決策。「不用 tracker／ReID」寫在契約 §1 與規格 §1.3。「不用外部 API」寫在契約 §1，D107-1 把這條稱為「D28『不用外部 API』」。本文沿用各條原出處。「隱私」這個理由在 repo 決策中**沒有找到對應的 D 編號**（`UNKNOWN`），§5 把它列為本文的定位論點，不當成既有決策。

## 2. 多鏡頭多目標追蹤（MTMC）

### 2.1 DukeMTMC 與 IDF1

- **Ristani, Solera, Zou, Cucchiara, Tomasi（Duke／Modena），“Performance Measures and a Data Set for Multi-Target, Multi-Camera Tracking”，ECCV 2016 Workshops，LNCS 9914，pp. 17–35。** [arXiv:1609.01775](https://arxiv.org/abs/1609.01775)；[ML Anthology](https://mlanthology.org/eccv/2016/ristani2016eccv-performance)。
  - 提出以身分為核心的 precision／recall 指標（後來通稱 IDF1）。
  - 釋出 DukeMTMC：8 台 1080p／60 fps 鏡頭、約 85 分鐘、2,700 多個身分。
- **撤回狀態。** 資料集在 2019 年 6 月下架，作者致歉，起因是在 Duke 校園未經同意拍攝學生。衍生的 DukeMTMC-reID 等資料集仍在流通。
  - 來源：[Princeton CITP 部落格（2020-10-21）](https://blog.citp.princeton.edu/2020/10/21/facial-recognition-datasets-are-being-widely-used-despite-being-taken-down-due-to-ethical-concerns-heres-how)、[Exposing.ai](https://exposing.ai/duke_mtmc/)。
  - NeurIPS 2020 有倫理審查意見認為接受的論文不應使用 DukeMTMC（[MetaReview](https://papers.nips.cc/paper/2020/file/821fa74b50ba3f7cba1e6c53e8fa6845-MetaReview.html)）。
  - 撤回的確切日期與發布者聲明原文：`UNKNOWN`（只有二手來源）。
- **與 Amidst 的關係。** 不使用 DukeMTMC 與其衍生集。IDF1 衡量身分一致性，Amidst 不輸出身分，所以 IDF1 不適用；Amidst 用逐事件決策窗評 Q5（D79）。

### 2.2 AI City Challenge

- **Wang 等（NVIDIA 等），“The 8th AI City Challenge”，CVPR 2024 Workshops。** [arXiv:2404.09432](https://arxiv.org/abs/2404.09432)；[CVF Open Access](https://openaccess.thecvf.com/content/CVPR2024W/AICity/html/Wang_The_8th_AI_City_Challenge_CVPRW_2024_paper.html)。
  - Track 1 是多鏡頭人物追蹤。資料是 NVIDIA Omniverse 合成的 6 個環境，953 台鏡頭、2,491 人。
  - **鏡頭有校正**，主辦方提供相機矩陣與 3D 標註。
  - 指標改成以 3D 位置計算的 HOTA，偏好線上方法。
- **Tang 等，“The 9th AI City Challenge”，ICCV 2025 Workshops。** [arXiv:2508.13564](https://arxiv.org/abs/2508.13564)；[CVF Open Access](https://openaccess.thecvf.com/content/ICCV2025W/AICity/html/Tang_The_9th_AI_City_Challenge_ICCVW_2025_paper.html)。Track 1 改成多類別 3D 多鏡頭感知，涵蓋人、人形機器人、AMR、叉車，合成鏡頭超過 500 台，附詳細校正與深度。
- **常見管線**（依 8th 摘要對前段隊伍的整理）：
  1. YOLO 系偵測，加姿態估計找腳點；
  2. 單鏡頭追蹤：BoT-SORT、StrongSORT、ByteTrack 等；
  3. ReID 特徵：OSNet、TransReID 等；
  4. 跨鏡頭關聯：維護全域 anchor，或做階層／凝聚式分群，加時空約束；
  5. 用校正矩陣把結果投到 3D。
- **與 Amidst 的關係。** AI City 的設定是校正過、大量合成鏡頭、輸出全域 ID 與 3D 位置。Amidst 的這三項都相反：未校正、只有 8 台、不輸出身分。所以 AI City 的指標與方法都不能直接拿來比，只當背景。

## 3. 多視角 3D 追蹤（重疊、校正）

### 3.1 NVIDIA DeepStream MV3DT

- **NVIDIA，DeepStream 8.0 “Multi-View 3D Tracking (MV3DT)”，Developer Preview。** [官方文件（archive）](https://archive.docs.nvidia.com/metropolis/deepstream/8.0/text/DS_MV3DT.html)。2026-11-01 讀取頁面確認：
  - **前提**：每台鏡頭都要校正，並共享全域座標；鏡頭之間要有**重疊視野**。
  - **架構**：完全分散式，沒有中央控制器。鏡頭只和視野相鄰的鏡頭以 **MQTT** 交換資料（目前只支援 MQTT）。
  - **跨鏡頭關聯**：比較相近時間戳的 tracklet 的 **3D 腳點**，用地面平均距離算分數 `1/(1+avgDist)`，超過門檻才配對。
  - **融合**：同伴量測通過內點檢查後（投影到自己的視野、可見度、和預測位置的距離），和自己的量測一起送進 **Kalman 濾波**，量測雜訊依可見度加權。
  - **全域 ID**：第一批看到目標的鏡頭透過 MQTT 協商出全域唯一 ID，再傳給相鄰鏡頭；發現關聯錯誤時會更正。
  - 文件的正式發布年份：`UNKNOWN`（頁面只標 DeepStream 8.0）。

### 3.2 重疊視野資料集

- **Chavdarova 等（EPFL／Idiap／ETH），“WILDTRACK: A Multi-Camera HD Dataset for Dense Unscripted Pedestrian Detection”，CVPR 2018，pp. 5030–5039。** [CVF Open Access](https://openaccess.thecvf.com/content_cvpr_2018/html/Chavdarova_WILDTRACK_A_Multi-Camera_CVPR_2018_paper.html)；早期版本 [arXiv:1707.09299](https://arxiv.org/abs/1707.09299)。
  - 7 台靜態鏡頭拍同一塊戶外空地，**視野嚴格重疊**，附內外參聯合校正。
  - 標註 400 幀（2 fps），共 4 萬多個框、300 多人。
  - 主要用途是多視角偵測。論文提到 PETS 2009 是先前最大的嚴格重疊資料集。
- 其他重疊資料集（例如 MultiviewX）本次沒有查證，不列入。

### 3.3 與 Amidst 的關係

MV3DT 與 WILDTRACK 都假設**校正＋重疊**。Amidst 第一版剛好缺這兩項：鏡頭不重疊（重疊接手延到第二版，D77、D90），而且不把校正外參用在推論。所以 3D 腳點關聯在第一版不能用。未來工作見 §8 第 1 項。

## 4. 鏡頭拓撲、camera link model 與不重疊鏡頭的時空推理

這是與 Amidst 最接近的研究脈絡。這類方法處理鏡頭之間的盲區，靠出口／入口的時空規律來關聯觀測。

| 工作 | 作者／機構 | 年份 | 出處 | 要點（依查到的摘要或二手描述） |
| --- | --- | --- | --- | --- |
| Bayesian Multi-Camera Surveillance | V. Kettnaker、R. Zabih（Cornell） | CVPR 1999 | [ML Anthology](https://mlanthology.org/cvpr/1999/kettnaker1999cvpr-bayesian)；DOI 10.1109/CVPR.1999.784638 | 不重疊鏡頭的路徑重建寫成貝氏問題，取後驗最大的路徑集合。頁碼來源不一致（`UNKNOWN`） |
| Tracking Across Multiple Cameras with Disjoint Views | O. Javed、Z. Rasheed、K. Shafique、M. Shah（UCF） | ICCV 2003 | [ML Anthology](https://mlanthology.org/iccv/2003/javed2003iccv-tracking)；DOI 10.1109/ICCV.2003.1238451 | 不重疊鏡頭之間的觀測在時間與空間上相隔很遠；學鏡頭之間的時空關係與外觀關係。轉移時間模型的細節沒有讀原文核對（`UNKNOWN`） |
| Bridging the Gaps Between Cameras | D. Makris、T. Ellis、J. Black（Kingston／City Univ. London） | CVPR 2004，pp. 205–210 | [ML Anthology](https://mlanthology.org/cvpr/2004/makris2004cvpr-bridging/)；DOI 10.1109/CVPR.2004.53 | 非監督學習網路的活動模型。依二手描述：以 GMM 學出入口區，再用出入事件的共現找出跨鏡頭連結與轉移時間 |
| Online-Learning-Based Human Tracking Across Non-Overlapping Cameras | Y. Lee、Z. Tang、J.-N. Hwang、Z. Fang（UW 等，依海報） | `UNKNOWN`（據稱 IEEE TCSVT 2018，未核對） | [UW 論文（Lee 2017，第 5 章）](https://digital.lib.washington.edu/researchworks/items/18c55fcc-4543-40c9-a250-fb4ace41186b/full)；[SigPort](https://sigport.org/node/1869) | 線上、非監督地估計 **camera link model**（含轉移時間），再搭配外觀特徵做跨鏡頭關聯。期刊卷期：`UNKNOWN` |

**與 Amidst 的對應：**

- Amidst 的 **Camera Transition Graph** 和這些方法的「出入口區＋鏡頭連結」是同一類結構。差別有兩點：
  1. Amidst 的圖是**人工核准、事件前凍結**（D68、D74），不是從軌跡統計學來。
  2. Amidst 目前只用「是否相鄰」與 D28 排序鍵，**沒有轉移時間分布**。Q5 的等待期限是參數組裡的固定值（契約 §11）。
- 這些經典方法最後都用外觀把人關聯起來，實際上就是做身分判斷。Amidst 不做這一步，跨鏡頭只到候選串接。

## 5. Tracker 與 ReID：主流做法，以及本系統為什麼不用

| 工作 | 作者／機構 | 年份 | 出處 | 要點 |
| --- | --- | --- | --- | --- |
| ByteTrack | Y. Zhang 等（華中科大、HKU、ByteDance） | ECCV 2022 | [arXiv:2110.06864](https://arxiv.org/abs/2110.06864)；[ECVA](https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/315_ECCV_2022_paper.php) | 低分偵測框也參與關聯，先配高分框，再用低分框補配。MOT17 test：80.3 MOTA、77.3 IDF1、63.1 HOTA |
| BoT-SORT | N. Aharon、R. Orfaig、B.-Z. Bobrovsky（Tel Aviv Univ.） | 2022（arXiv） | [arXiv:2206.14651](https://arxiv.org/abs/2206.14651) | 在 ByteTrack 上加鏡頭運動補償、改良的 Kalman 狀態，可選 ReID。正式會議／期刊：`UNKNOWN` |
| OSNet | K. Zhou、Y. Yang、A. Cavallaro、T. Xiang（QMUL／Surrey 等） | ICCV 2019 | [CVF Open Access](https://openaccess.thecvf.com/content_ICCV_2019/papers/Zhou_Omni-Scale_Feature_Learning_for_Person_Re-Identification_ICCV_2019_paper.pdf)；[arXiv:1905.00953](https://arxiv.org/abs/1905.00953) | 全尺度的輕量 ReID 骨幹，約 2.2M 參數 |

**為什麼第一版不用。** 依現有決策整理；最後一點是本文的論點：

1. **範圍。** 契約 §1 與規格 §1.3 明列第一版不做 ByteTrack／OSNet／ReID，也不做跨鏡頭身分確認。
2. **不做身分確認。** `identity_verdict` 一律 `UNCONFIRMED`（契約 §1）。ReID 的輸出是外觀相似度，等於身分判斷，這和契約的身分邊界衝突。
3. **可重現、可解釋。** 候選由兩層圖加 D28 決定性產生，偵測數、顏色與 LLM 都不進排序（契約 §5.4）。每一步都能用預錄回放重現（AC1、AC7）。學習式 tracker 的 ID 切換和 ReID 的相似度門檻，會讓「為什麼切到這台」難以用規則逐步交代。
4. **隱私（本文論點，非既有決策）。** DukeMTMC 撤回（§2.1）說明，蒐集與使用外觀身分特徵有倫理風險。Amidst 只用類別、框與顏色，不建外觀身分特徵庫，風險比較小。這點在 repo 決策裡**沒有對應的 D 編號**，只是定位論點。

## 6. 自然語言檢索影片與 LLM 解析查詢（對應 Q3）

| 工作 | 作者／機構 | 年份 | 出處 | 要點 |
| --- | --- | --- | --- | --- |
| CityFlow-NL | Q. Feng、V. Ablavsky、S. Sclaroff（Boston Univ.） | 2021（arXiv） | [arXiv:2101.04741](https://arxiv.org/abs/2101.04741) | 用自然語言描述檢索車輛軌跡：666 輛目標車、3,028 條單視角軌跡、40 台校正鏡頭、5,289 條描述。AI City Challenge 2021 起的自然語言車輛檢索賽道採用 |
| CLIP4Clip | H. Luo 等（西南交大、Microsoft 等） | 2021（arXiv） | [arXiv:2104.08860](https://arxiv.org/abs/2104.08860) | 把 CLIP 用於端到端的文字—影片片段檢索（MSR-VTT 等） |
| NVIDIA Blueprint for Video Search and Summarization（VSS） | NVIDIA | 文件 3.x；年份 `UNKNOWN` | [官方文件](https://docs.nvidia.com/vss/3.0.0/overview/latest)；[GitHub](https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization) | 結合 VLM、embedding 語意搜尋、RAG 與 Agent，做片段檢索與長影片摘要 |

**與 Amidst 的關係：**

- 上面這些工作用**學習式的跨模態嵌入**或 VLM，直接比對文字和畫面。
- Amidst 的 Q3 做法不同：先用規則語法，或本機 Qwen 把中文句子**解析成結構化查詢**（類別、顏色、時間、找或追），再交給決定性的 Q1／Q2 去讀離線偵測索引（契約 §7）。LLM 不看畫面，也不排序。
- 這樣做的優點是可稽核、可重播；代價是描述能力受限於支援類別表與 HSV 顏色。
- 「用 LLM 把監控查詢解析成結構化過濾條件」這個具體做法，本次**沒有找到可以直接對照、經同儕審查的代表作**（`UNKNOWN`）。

## 7. 定位表

| 面向 | MTMC 管線（AI City） | 多視角 3D（MV3DT、WILDTRACK） | 鏡頭拓撲／camera link model | 文字—影片檢索（CityFlow-NL、CLIP4Clip、VSS） | **Amidst 第一版** |
| --- | --- | --- | --- | --- | --- |
| 要解的問題 | 所有人的全域軌跡與 ID | 重疊區的 3D 位置與全域 ID | 跨盲區把同一人串起來 | 依文字找片段或軌跡 | 目標離開鏡頭後**該不該切、切哪台**（Q5），加上依條件找鏡頭或人（Q1–Q3） |
| 輸入需求 | 偵測、單鏡頭 tracker、ReID、通常有校正 | 偵測、tracker、每台校正、MQTT | 長期軌跡，用來學出入口與轉移時間 | 大量文字—影片配對或 VLM | 離線偵測＋HSV，加人工核准的兩層圖 |
| 校正 | 通常需要（3D HOTA） | **必需** | 不一定 | 不需要 | **推論不用** |
| 視野重疊 | 混合 | **必需** | 不重疊 | 不涉及 | **多半不重疊**（重疊接手是第二版） |
| 身分 | 輸出全域 ID | 輸出全域 ID | 外觀關聯，實質是身分 | 不一定 | **`UNCONFIRMED`**，只做候選串接 |
| 盲區處理 | 時空約束＋外觀 | 不處理（靠重疊） | 轉移時間分布 | 不處理 | 狀態機加出口／相鄰轉移；沒有觀測就標 `MISSING`／`UNKNOWN` |
| 輸出 | 軌跡、ID、指標 | 3D 軌跡、ID | 跨鏡頭配對 | 排名結果 | 切鏡決策、候選與證據，逐步紀錄 |
| 可重現性 | 依實作，學習式元件多 | 線上、分散式 | 依學到的模型 | 依模型 | 決定性排序、hash 綁定，預錄回放 |

**一句話定位：Amidst 解的是不重疊、未校正鏡頭之間的盲區切鏡與輔助檢索，不確認身分，每一步都可回放。**它不跟 MTMC 或 MV3DT 比追蹤精度，因為輸入條件和輸出目標都不同。

## 8. 可借鏡的未來工作

以下每項都是**未來工作，不在 11-04 demo 範圍**，也不構成提案或決策。

1. **重疊鏡頭對（OV 類）：參考 MV3DT 的 3D 腳點關聯。**
   - 若有使用者核准、可用於推論的校正資料，重疊對之間可以比較同時段偵測的地面腳點距離，當作「同一目標」的幾何證據。依 MV3DT 的分數形式，就是 `1/(1+平均地面距離)` 超過門檻。
   - 這只能是證據，不能變成身分；仍標 `UNCONFIRMED`。
   - 目前 OV1 只展示、不計分（D105-2），並帶 `OVERLAP_P_OV2_UNVERIFIED` 標籤。
2. **用 camera link model 改進物理預測的時間窗。**
   - 參考 Makris 2004、Javed 2003、Lee（camera link model）：對每條核准的相鄰轉移，估計轉移時間分布，取代固定的等待期限。
   - 如此一來，D107-1 的物理預測與 Q5 的搜尋時間窗都可以隨轉移邊調整。
   - 估計只能用偵測結果，不得用 GT 或渲染軌跡；估計出的分布要綁 hash，才能重播。
3. **身分一致性指標。** 若之後真的要做身分（目前不在範圍），應該先由使用者決定，再考慮 IDF1／HOTA。不可使用 DukeMTMC 及其衍生集（§2.1）。
4. **Q3 與學習式檢索。** CLIP4Clip 或 VSS 這類嵌入檢索，可以當 Q1 的比較組，處理顏色以外的屬性描述。要先決定外部模型與資料邊界（契約 §1；D107 的例外只限俯視圖）。

## 9. 來源與查證狀態

「已查證」表示在 2026-11-01 用網路搜尋找到出處頁，並核對了作者與年份；「部分」表示有欄位是 `UNKNOWN`。

| # | 來源 | 狀態 | UNKNOWN 欄位 |
| --- | --- | --- | --- |
| 1 | Ristani 等 2016（DukeMTMC、IDF1） | 已查證 | — |
| 2 | DukeMTMC 撤回（CITP 部落格、Exposing.ai、NeurIPS 2020 MetaReview） | 部分 | 撤回的確切日期與作者聲明原文只有二手來源 |
| 3 | Wang 等 2024，8th AI City Challenge | 已查證 | — |
| 4 | Tang 等 2025，9th AI City Challenge | 已查證 | — |
| 5 | NVIDIA DeepStream 8.0 MV3DT 文件 | 已查證（讀取頁面） | 文件發布年份 |
| 6 | Chavdarova 等 2018，WILDTRACK | 已查證 | — |
| 7 | Kettnaker、Zabih 1999 | 部分 | 頁碼（來源不一致） |
| 8 | Javed 等 2003 | 部分 | 轉移時間模型的細節（沒讀原文） |
| 9 | Makris、Ellis、Black 2004 | 部分 | 方法細節只來自二手描述 |
| 10 | Lee、Tang、Hwang、Fang，camera link model | 部分 | 期刊、年份、卷期（TCSVT 2018 未核對） |
| 11 | Zhang 等 2022，ByteTrack | 已查證 | — |
| 12 | Aharon 等 2022，BoT-SORT | 部分 | 正式發表處 |
| 13 | Zhou 等 2019，OSNet | 已查證 | — |
| 14 | Feng 等 2021，CityFlow-NL | 已查證 | — |
| 15 | Luo 等 2021，CLIP4Clip | 已查證 | — |
| 16 | NVIDIA VSS Blueprint | 部分 | 年份 |
| 17 | LLM 解析監控查詢的代表作 | `UNKNOWN` | 沒有找到 |

合計 17 項：已查證 9 項、部分 7 項、完全 `UNKNOWN` 1 項。

**本系統元件（不屬於相關工作，只列出處）：** RT-DETR，Lv／Zhao 等（Baidu），“DETRs Beat YOLOs on Real-time Object Detection”，[arXiv:2304.08069](https://arxiv.org/abs/2304.08069)；正式會議（CVPR 2024）本次沒有核對到（`UNKNOWN`）。Qwen 的版本與 digest 以契約與 parameter_set 為準，本文不列。
