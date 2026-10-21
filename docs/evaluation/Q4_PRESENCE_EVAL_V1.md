# Q4 抽樣與人工 T/F 評估程式 v1

Refs #123、#128、#147。程式由 Codex 依本次工作清單交付；人工看圖、填T/F及定門檻由組員／使用者做。本文件不提供題目或標準答案。正式 A4／B4 指標 **NOT_RUN**：#118正式索引與組員標註尚未完成。

## 先凍結輸出，再抽樣與標註

輸入是已凍結的系統說法JSONL，每行包含 run_id、clock_id、camera_id、frame_index、rgb_file_sha256、polarity（bool）、statement、prediction_ref、prediction_sha256。`polarity=true`代表系統說有，false代表系統說沒有，不是人工答案。類別／衣色語意由凍結說法定義，評分器不從文字猜類別或替系統改說法。

先宣告 seed、樣本總數（正偶數），記錄輸入檔SHA與抽樣規則，再交組員。依 `SHA256(canonical({seed, key:[run,camera,frame,statement]}))` 排序，有／沒有各抽一半、不放回；任一層不足時兩層同步縮減，報shortfall。和#147 builder使用相同鍵、hash與排序，可將抽樣計畫的selected交給builder（它對已選集合再次排序，不改集合）。不同版本／不同seed須另記，不事後挑選。

每個statement可以是人物、車或指定衣色判斷；抽樣計畫**必定含有及沒有兩層**，沒有單一層時拒絕。此版未實作額外的camera/class/color配額，不宣稱每類樣本數相等。`UNKNOWN`不能冒填false；如需審UNKNOWN，須另立明確說法與抽樣層，不能混成「沒有」。

```bash
PYTHONPATH=src python scripts/eval_q4_presence.py sample \
  --claims <frozen-claims.jsonl> --claims-sha256 <trusted-sha256> \
  --count <positive-even-count> --seed <predeclared-seed> --output <new-plan.json>
```

先以#147 builder交圖與鎖定的說法，組員填CSV；再用#147 importer驗原MANIFEST／圖片／範本與不可改欄位，記錄回收CSV的新hash。這遵循使用者已確認的回收方式；評估器不重寫CSV、索引或模型輸出。

## T/F 的算式與分母

讀#147 importer的 `q4_tf_review_v1.jsonl`（每列schema `q4-tf-review.v1`）和原 `MANIFEST.json`，兩個輸入都須提供可信SHA。評分前驗sample_id唯一及屬於MANIFEST，run/camera/frame、RGB pin、prediction pin、system_positive、PILOT/正式狀態與frame_ref一致。

| 系統說法 | 組員填 | 實際presence（限該說法） | 混淆格 |
|---|---|---|---|
| 有 | T | 有 | TP |
| 有 | F | 沒有 | FP |
| 沒有 | T | 沒有 | TN |
| 沒有 | F | 有 | FN |
| 任一 | 不確定 | UNKNOWN | 排除於正式決定分母 |

以上是布林算式，不是任何影像的標準答案。「沒有」說法也必須看圖，不能因模型沒框就填T。PILOT即使填T/F也不進正式分母；不確定不當F或TN。缺審列計missing_review_count，不能補成負例。重複／越界ID、改動來源、非法答案或PILOT狀態衝突直接拒絕，不輸出誤導報告。#147已標INVALID的列不進review JSONL，會反映為missing，原invalid_rows仍須另查。

報告含TP/FP/TN/FN、precision/recall/accuracy各自分子分母、review與formal-decided coverage、PILOT/不確定排除數、缺審數、有／沒有說法數、run+camera與prediction hash分組，以及逐sample計數理由。不猜自然語言類別，因此沒有杜撰各色準確率；可對預先固定的單一claim種類分別產包再報告。分母0時value=null，不稱0%或通過。

```bash
PYTHONPATH=src python scripts/eval_q4_presence.py score \
  --reviews <q4_tf_review_v1.jsonl> --reviews-sha256 <trusted-import-output-sha256> \
  --manifest <MANIFEST.json> --manifest-sha256 <trusted-manifest-sha256> \
  --output <new-report.json>
```

輸出檔只可新建，拒絕覆寫。報告只記輸入hash、不帶本機絕對路徑或實時計時；canonical output_sha256排除自身，同輸入重跑可重現。空review可報NO_FORMAL_LABELS與全數缺審；沒有自動補答案。CLI不是T/F填寫介面，組員仍只填#147 CSV。

## 解讀限制與驗證

這些數字描述**有／沒有平衡抽樣且已決定的人工審核子集**；未按來源母體比例加權，缺審／不確定也可能造成選擇偏差，不能當整個run的真實precision/recall。偵測缺失不等於人物不在，不證明身分、跨鏡頭追蹤、盲區路線或物理通行。沒有通過門檻、調參、GT／劇本讀取、RGB讀取、模型呼叫或回灌推論的入口。

指定focused：`pytest tests/unit/test_q4_presence_eval.py`；`git diff --check`。測試只造最小布林記錄驗算四格、缺審、不確定、PILOT、來源篡改及抽樣不放回，沒有寫人用影像題庫／標準答案。#127對此離線評估報告沒有schema，N/A；不可把#127自測當正式辨識驗收。真正T/F、正式r004、類別衣色品質仍待組員與Claude檢查。
