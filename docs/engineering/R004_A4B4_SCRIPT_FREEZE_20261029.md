# A4-1／B4-1 劇本凍結候選（CQ-24，2026-10-29）

**PROPOSED／PENDING_USER，production_ready=false；沒有凍結、核准或渲染。** 本文件只固定候選輸入與當前計分分支，不是正式答案或runtime輸入。
source `.blend`僅沿用既有hash，原檔未開啟；所有producer保持UNFROZEN_DRAFT_NOT_EXECUTABLE、execution=false、freeze_sha256=null。

## 固定來源與依賴

PR base採#254分支；依D97以feature merge保存其餘4個前置歷史，沒有合併任何PR或改staging。
依賴未經 Claude 複審：#295@20118373170e64718bb00cbd75cc58d0434d535f。
依賴未經 Claude 複審：#275@5ceedac1dc6e72cbafdd24c59c24f97c041f22d5。
依賴未經 Claude 複審：#256@c8f6f42fbd13b779fb85ac094ed6ed234b9caa48。
依賴未經 Claude 複審：#254@3ccfc556b183e53d4ef7ca13b6119a92ba27798e。
依賴未經 Claude 複審：#294@0c34287b0b0c21c672f863fd281934f37e8aa24b。

| 來源 | bytes SHA-256 |
| --- | --- |
| `configs/q1q5/scripts/r004_a4_1_script_draft_v1.json` | `d304d0fcc17932e11dd54120fc06f88c96e28dbb07713c75e388e7664a4824a9` |
| `configs/evaluation/r004_a4_1_script_plan_v1.json` | `26771d683a0e10a36fc0b498069f1161901744bfbc1b1f57919f8181c055d754` |
| `configs/q1q5/clocks/r004_a4_v1.json` | `a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a` |
| `configs/q1q5/runs/r004_a4_v1.json` | `2f9c77fac097098787a1b23602cc59868677d655a1c4f92c0831c21f9dd0a0b9` |
| `configs/q1q5/scripts/r004_b4_1_script_draft_v1.json` | `c1e7dcd1461f646c532fdd85d6f59c81ae9155cc14bcaf3c3b0a5ba2865c8345` |
| `configs/evaluation/r004_b4_1_script_plan_v1.json` | `b2f78e591c5086b4d51c237caf327190332a79ea7b067230ed682fbaeb80cf93` |
| `configs/q1q5/clocks/r004_b4_v1.json` | `3a39443753120c102acaf23ed7c166048157f4ae805d92ff12f36e45a31c35d4` |
| `configs/q1q5/runs/r004_b4_v1.json` | `bec1b2829ef2eabcdac74ea9123725ee7e9b486364c27c360b45e70eb707b598` |
| `configs/q1q5/graphs/r004/camera_graph_v3_1.json` | `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409` |
| `configs/q1q5/graphs/r004/region_graph_v3_1.json` | `a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1` |
| `configs/q1q5/graphs/r004/tracking_scope_v3_1.json` | `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a` |
| catalog（D84；bytes pin） | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| source `.blend`（僅既有pin） | `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` |

producer一詞在此指兩份已交件的不可執行規劃JSON；未新增可執行render script或複製私有執行器／資產。

## D96-1逐條結論

| 事件 | 來源與條件 | 結論 |
| --- | --- | --- |
| A4-c2 | #256@c8f6f42fbd13b779fb85ac094ed6ed234b9caa48；`D96_validation.selected_t_V_necessary_condition=FAIL`，全身可見性UNKNOWN。選定參考線的W1上部見證約37.651833s早於38.4s | 維持不計分；未取得可驗證的完整恢復條件 |
| B4-e | #275@5ceedac1dc6e72cbafdd24c59c24f97c041f22d5；W1軸點最後30.062834s、W2最後31.961250s（>31.0）、R101_IN首30.0s（<31.4），全身／實際觀測仍UNKNOWN | 維持不計分；軸點不能代替完整body或實測 |

兩個`verification_ref`都在JSON列出PR、head、evidence_file bytes pin與section，檢查器驗原檔bytes。A4-e／B4-d依D92-1固定不計分。
目前4個計分候選（A4兩個、B4兩個），不是4個事件已獲正式接受。A4 producer內D92合計5個的summary保留歷史bytes；本候選依D96與#254當前plans明列合計4個，不把過期summary當現況。

## 事件與時鐘

A4 run長度50s、query[0,48)s；B4 run長度42s、query[0,40)s；5fps、sample interval=200000us。相鄰計分窗依D79由既有adapter重新導出，不讀render輸出。

| 場次 | 事件 | 預期動作 | t_X秒 | t_N秒 | 當前分支 |
| --- | --- | --- | ---: | ---: | --- |
| A4-1 | A4-c1 | SWITCH | 8 | 11.0 | 計分候選 |
| A4-1 | A4-n1 | NO_SWITCH | 16 | — | 計分候選 |
| A4-1 | A4-e | SWITCH | 26 | 29.0 | 不計分 |
| A4-1 | A4-c2 | SWITCH | 36 | 39.0 | 不計分 |
| B4-1 | B4-n1 | NO_SWITCH | 4 | — | 計分候選 |
| B4-1 | B4-b | SWITCH | 11 | 14.0 | 計分候選 |
| B4-1 | B4-d | SWITCH | 21 | 24.0 | 不計分 |
| B4-1 | B4-e | SWITCH | 30 | 32.0 | 不計分 |

兩場各保留3次計畫SEARCHING（含不計分事件），不計分不會刪掉產品動作或搜尋預算。CAM_ENTRY只留在A4查找／素材範圍，不在自動切鏡候選或seed。
5fps格點檢查對象是run samples與評分anchors。producer的連續路線控制點保持原微秒值與hash，不擅自四捨五入、移動時刻或改路線。

## 檢查器與重現

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_r004_script_freeze.py tests/unit/test_q5_script_adapter.py
uv run python scripts/check_r004_script_freeze.py --freeze docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json
```

檢查器只接受待核候選。時鐘長度、格點、來源／run／camera pins、事件範圍、D79窗、D92／D96不計分名單、宣告數與三次搜尋、CAM_ENTRY排除，以及producer／adapter逐事件錨點都必須一致；一個已pin檔案byte改動即拒絕。
`--expected-freeze-sha256 <PR記錄的JSON bytes SHA>`可額外驗候選本身的原始bytes；這也會拒絕只改空白的byte差異。不能從沒有外部pin的文件自宣告人類核准。

## Safe bundle：未物化，不能宣稱通過

本候選兩run註冊仍DECLARED_NOT_RENDERED／rendered=false，因此`safe_bundle_manifests=[]`、materialization=NOT_MATERIALIZED。檢查器單列privacy狀態NOT_RUN／MISSING，privacy_verified=false；candidate_status=PASS只表示候選與已提供輸入自洽，**不等於safe bundle PASS、不解除凍結或渲染gate**。
有materialized manifest時必須明列path與bytes SHA，提供了卻缺檔／壞pin就FAIL；任何nested欄位含producer或adapter劇本檔名／hash（含大寫hash）即FAIL。候選檔名與hash也不得洩漏進manifest。此拒絕行為用SYNTHETIC正反例驗證，本次沒有產製safe bundle。

## 等使用者與下游

PR內附「A4-1／B4-1劇本凍結核准」checkpoint內文草稿；本任務不自行開checkpoint。使用者須明確核准固定候選hash及兩份producer／plan pins，未核前狀態保持PENDING_USER。
G4、U4凍結與D98-2磁碟≥9GiB全部成立後，#115才可依既有授權進行；本候選不替代G4、不自行啟動render。劇本／private keyframes不得進入推論或safe bundle。
ARCH #307尚未交付且blocked-user，本次架構守門NOT_RUN；沒有新recorded輸出，#127 kit NOT_RUN。既有v1評分器bytes不變。
