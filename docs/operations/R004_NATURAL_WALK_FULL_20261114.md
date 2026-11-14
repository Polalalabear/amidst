# #516 完整步態修正版：A4／B4，5 fps

使用者確認小幅腳步與修正後的手臂方向，要求看完整版本，並明確選擇5fps。已完成A4的50秒、B4的42秒；保持v2.2原路線、事件時刻、相機與材質。新影格與影片全放LOCAL，原#523資料、索引、bundle與8785未切換。

## 觀看與產物

路徑均相對於 `$AMIDST_ARTIFACTS`（服務repo的`local/`）。

- 入口：`evidence/codex-516-natural-walk-full-20261114/REVIEW_FULL.html`。可展開九個鏡頭的完整960×540影片。
- A4拼接：`evidence/codex-516-natural-walk-full-20261114/A4-1_full_corrected_5fps.mp4`，50秒／250格／5fps；1,187,829 bytes，SHA-256 `5c7f101bc69c4104f9990ca81aeaed482971148ebaec942a62c4b4a86a958fbc`。
- B4拼接：`evidence/codex-516-natural-walk-full-20261114/B4-1_full_corrected_5fps.mp4`，42秒／210格／5fps；1,397,601 bytes，SHA-256 `2e70d0fb58e61001f9ac14cd2df969bb32d194193089b34e3cca22e52f17c818`。
- 全部新RGB：`data/r004-4actor-natural-walk-20261114/`。A4四鏡×250＝1,000張；B4五鏡×210＝1,050張，共2,050張。沒有用舊run像素補缺。
- 固定manifest：`evidence/codex-516-natural-walk-full-20261114/FULL_MANIFEST.json`，**2,166檔／1,131,146,095 bytes**，SHA-256 **`65f1824bec1eed94d7e20a4a49d50d49540bf77c6e85b2d1b7caf24751777b7f`**。同本PR的`R004_NATURAL_WALK_FULL_MANIFEST_20261114.json`。包含新RGB、11支影片（兩支拼接＋九支單鏡頭）、完整檢查／journal／程式快照；後續CI／結案紀錄不屬固定payload。

拼接固定列出7個追蹤鏡頭加CAM_ENTRY。A4實際產製EXT_CAR／EXT_CLEAR／ENTRY／W1；B4實際產製W1／W2／BRANCH／R101_IN／WIDE。沒有產製的槽位明示「未產製」，不是「無人」。影片標source elapsed與原宣告展示時鐘；最後取樣為49.8／41.8秒，沒有額外插補終點。

## 動作與本次檢查

- 走路抬腳1.8cm、單腿週期行進距離0.85m、支撐比例0.55。平直1m/s測試最大屈膝約33.4°；這不是所有轉彎／地板高差的上界。
- 手臂IK pole由`[1,0,0]`改為`[-1,0,0]`；手肘向後彎，擺臂由對側腳的前後領先差驅動。腳、髖部、root xyz/yaw、速度等非手臂欄位，相對已確認的小幅度版本共4,796姿態逐項相同。
- 詳細原值→新值與兩輪使用者回饋保留在同PR的`R004_NATURAL_WALK_SAMPLE_20261113.md`；先前所有LOCAL樣片保留。
- 未修改的`check_actor_clearance.py`重跑：A4／B4均exit0、各7項PASS，名義牆距／障礙距政策≥0.35m。不是全身各處距表面≥0.35m的證明。
- 新姿態端點audit：12個first/last端點、共54個實際渲染鏡頭檢查皆PASS；含錄影結束的較嚴終點條件及B4 A/B的W_HOOD遮擋。使用完整mesh三角形的視錐裁切／凸靜態遮擋證明，不以少量射線樣本宣稱通過，不用其他人物遮擋。
- 全時段5fps的mesh檢查：A4 250、B4 210個全域時刻，所有當時存在的人物對可見牆／屏風／車體及不同人物之間，表面相交0 findings。不是連續時間、完整封閉體包含或物理導航驗收；地面不列為牆體，以容許腳掌接觸。
- 每個相機全部影格重新做mesh檢查、SHA／大小journal與8GiB＋32MiB逐格空間檢查。完成250／210格後才寫render receipt；中斷可用相同source/code/clock lock驗SHA後resume，不接受跨版本混接或未記錄影格。
- 全部2,050張PNG尺寸960×540、RGB、格點與journal SHA／大小核對通過；11支MP4全部完整decode、影格數與50／42秒時長通過。原相機matrix／fx差值0、source blend與catalog SHA不變。
- 最終聚焦測試12 passed：10項步態／手臂性質，加上2項完整產製CLI拒絕修改凍結資料夾的測試。完整CI以PR最後head的checks為準。
- 開始前`df -k ~`：16,142,472KiB（約15.39GiB）；完成渲染後14,283,808KiB（約13.62GiB）。啟動要求8GiB＋1.7GiB估計，逐格檢查未觸發停止線；這兩個df值不是全程最低值，也不能把差值全算成本產物大小。

主要收據位於同一LOCAL evidence目錄：`CLEARANCE_FULL.json`、`ENDPOINTS_FULL.json`、`A4-1-probe/probe.json`、`B4-1-probe/probe.json`、`PREFLIGHT_PASS.json`、`FULL_MEDIA_A4-1.json`、`FULL_MEDIA_B4-1.json`。逐檔SHA見固定manifest。

## 來源與執行版本

- 原blend SHA `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`；catalog SHA `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`。
- v2.2劇本SHA `14fc3a1eee450923ce799e2e6ca32adae99d8f25afc2dce7a210fb78776eef6c`；原v2.1／v2.2／checker與#520關卡未改。
- 影像產製執行commit：`745fb3f2`；已確認步態核心來自`9d2f8b4c`。影片編碼／固定manifest產製執行commit：`01bf013e`。每個render lock、receipt、FULL_MEDIA和payload的`code/`快照另外記錄實際程式SHA。
- 收尾再補了可指定全新data／evidence根目錄的重現選項，以及拒絕寫入已有`FULL_MANIFEST.json`的凍結目錄；沒有因此重渲染或改動已完成影片。實際執行快照在固定payload，最後Git head可由PR查到。
- `FULL_MEDIA_*.json`記錄獨立display run／clock ID，承接原宣告展示時鐘並保留parent clock SHA；不是將舊run ID套到新像素。

## 本次範圍與未驗證

這次是使用者要求的**完整觀看版**。沒有執行RT-DETR、local track、Agent、ranking或reconstruction，也沒有把新RGB換進舊索引／safe bundle。若採用這批新像素作推論資料，需另建對應run的索引與收據，不能混用#523舊records。

沒有讀renderer GT、trajectory、visibility或depth檔；作者路線與靜態幾何只供producer／設計檢查。原始blend不存檔／不複製；沒有新增跑步、跑進房間或車旁徘徊的路線。保留T的作者事件時刻，但姿態可能影響逐格遮擋／偵測，未宣稱實際LOST／RETURN、顏色或歧義段數重新驗收。原#523 G1/G2 PASS不直接替代新像素的推論驗收。物理導航仍UNKNOWN，正式研究／身分確認仍未通過。

## 重現（Mac、既有資產、全新輸出）

所有程式操作在user指定的shared scratch clone；不在8785服務checkout改tracked檔案、切分支或commit。原始資產只讀。已完成資料夾含`FULL_MANIFEST.json`，程式會拒絕覆寫；以下另選REPRO路徑。

```sh
export AMIDST_ARTIFACTS="$HOME/amidst/local"
export WALK_REPO=/tmp/codex-516-full-repro
git clone --shared "$HOME/amidst" "$WALK_REPO"
git -C "$WALK_REPO" remote set-url origin https://github.com/Polalalabear/amidst.git
git -C "$WALK_REPO" fetch origin codex/516-natural-walk-sample
git -C "$WALK_REPO" switch --detach origin/codex/516-natural-walk-sample
cd "$WALK_REPO"
export WALK_PYTHON="$HOME/amidst/.venv/bin/python"
export WALK_FFMPEG="$HOME/amidst/.venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
export WALK_EVIDENCE="$AMIDST_ARTIFACTS/evidence/codex-516-natural-walk-full-REPRO"
export WALK_DATA="$AMIDST_ARTIFACTS/data/r004-4actor-natural-walk-REPRO"
df -k ~
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B -m pytest tests/evaluation/test_r004_natural_walk.py -o addopts='' -q
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B scripts/produce_r004_natural_walk_full.py --repo "$WALK_REPO" --artifacts-root "$AMIDST_ARTIFACTS" --evidence-root "$WALK_EVIDENCE" --data-root "$WALK_DATA" --stage preflight
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B scripts/produce_r004_natural_walk_full.py --repo "$WALK_REPO" --artifacts-root "$AMIDST_ARTIFACTS" --evidence-root "$WALK_EVIDENCE" --data-root "$WALK_DATA" --stage render
uv --no-cache run --offline --no-project --python "$WALK_PYTHON" python -B scripts/package_r004_natural_walk_full.py --artifacts-root "$AMIDST_ARTIFACTS" --evidence-root "$WALK_EVIDENCE" --data-root "$WALK_DATA" --ffmpeg "$WALK_FFMPEG" --scene all
```

需要Blender5.2.1、既有Python／Pillow／imageio-ffmpeg，以及#523的唯讀appearance snapshot。GPU／encoder差異可能改變bytes，不承諾跨機逐位元相同；本次產物以已提交manifest驗證。重現後依scratch clone規則刪除暫存clone，保留LOCAL產物及GitHub分支。所有啟動／重現文件已上GitHub，實際RGB／影片全LOCAL。
