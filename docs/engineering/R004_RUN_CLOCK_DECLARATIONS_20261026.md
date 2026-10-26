# r004 A4／B4 獨立展示時鐘宣告

依使用者 2026-10-26 在 baseline 對話的明確選擇，A4、B4 各有獨立 run_id／clock_id，時區 Asia/Taipei，分別起於 2026-11-01 14:00 與 14:10。這是 `DECLARED_DEMO_CLOCK`，不是拍攝日期或人物事件時間；未沿用 A／B1 的歷史示例。

| run | run_id | clock_id | wall_origin | 來源範圍 |
| --- | --- | --- | --- | --- |
| A4 | ctrl-lcorr-s1-a4-5fps-v1-r004 | clock:r004:a4:declared-demo:v1 | 2026-11-01T14:00:00+08:00 | [0,30000000) us |
| B4 | ctrl-lcorr-s1-b4-5fps-v1-r004 | clock:r004:b4:declared-demo:v1 | 2026-11-01T14:10:00+08:00 | [0,30000000) us |

`t0_us=0`、`rate=1`；30秒與5fps沿用既有 r004 設計，不宣稱影像已產製。不是共用起點，兩 run 不串接人物身分。

## 檔案與 pins

- A4：[r004_a4_v1.json](../../configs/q1q5/clocks/r004_a4_v1.json)，file SHA-256 `8fd2cd78ac031bde37d999c173d020e08a41051027054a61f568a1226d7743cb`；content SHA `44bedb48a753ba5db0f948b98c2269d1a84e1d369e2093366bbf1a344ba09c89`。
- B4：[r004_b4_v1.json](../../configs/q1q5/clocks/r004_b4_v1.json)，file SHA-256 `eb8135c2767216025e33adca94081679c467305d9a3a8301ede3711f3bae8b0d`；content SHA `8cb773eec9f3bb8c8215ce75032c8dbedc0de4c006e64c9a85d51daff9290818`。
- context：[r004_formal_context_v1.json](../../configs/q1q5/r004_formal_context_v1.json)，file SHA-256 `46b24adbebb6d81462dcaf30cf29793ba598fcf69da09ab91dd160f2c90801bd`。含宣告 pin、來源 catalog pin、核定狀態與打包阻擋；不是正式 runtime registry。
- camera catalog 的來源 byte SHA-256：`3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`，8台，綁原包 MANIFEST `531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4`。只讀來源 JSON 核 hash，沒有複製或改校正資產。

catalog 的狀態是 **PINNED_CANDIDATE_PENDING_CLAUDE_AND_G4**，`frozen_file_sha256`／approval_ref 仍 null。這個來源 hash 不是凍結核准；G4 仍等 yyin 三題澄清併入圖複核與必要核定。Claude 核對時鐘／catalog 之後，還要記錄適用的凍結收據，才能解除 D80 的組員出題包硬前提。此 PR 不渲染、不正式發包，不建立正式 RGB／索引或成績。

## 重現驗證

使用既有 Python，不安裝依賴：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-sync python - <<'PY'
import hashlib, json
from pathlib import Path
from amidst.q1q5.clock_mapping import ClockMapping, resolve_source_range
context = json.loads(Path('configs/q1q5/r004_formal_context_v1.json').read_text())
assert len({r['run_id'] for r in context['runs']}) == 2
assert len({r['clock_id'] for r in context['runs']}) == 2
for row in context['runs']:
    raw = Path(row['clock_mapping_ref']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['clock_mapping_file_sha256']
    mapping = ClockMapping.from_document(json.loads(raw), expected_run_id=row['run_id'],
        expected_clock_id=row['clock_id'], expected_sha256=row['clock_mapping_content_sha256'])
    resolved = resolve_source_range(mapping, 0, 30000000)
    assert resolved.status == 'READY' and resolved.coverage_complete
assert not context['question_pack_ready'] and not context['G4_approved']
assert context['camera_catalog']['frozen_file_sha256'] is None
print('2 clock declarations PASS; catalog freeze and question pack remain BLOCKED')
PY
```

實際使用離線 uv／既有 Python3.12 執行同樣的 ClockMapping 與半開範圍檢查，2/2 PASS；validator來源與 staging@63ce04d 相同，SHA-256 `4129d88716a4cdaabc1a00928060c16fcda5505af2c24f81b6f4eee8f565b838`。不是模型／圖／辨識驗收。

## 實際產出 / Actual output

- Model / effort: GPT-6 / UNKNOWN。
- PR / commits: 本 Draft，base staging@63ce04df035fe2f5b02481da9757277f66ae5db6，精確 head 見 PR。
- Files changed: 兩份 clocks、formal_context、本文與 `docs/history/R004_FORMAL_CONTEXT_20261026.json`。
- Commands run and results: ClockMapping.from_document＋resolve_source_range 2/2 PASS；兩份獨立 ID／content/file hash、8台 catalog 與原 MANIFEST pin 核對 PASS；JSON解析／相對連結／git diff --check PASS。
- Artifacts: 上述公開 JSON／精簡收據；原 catalog／校正／RGB／原審查包 LOCAL，不上傳。
- Verified: 使用者新指定時鐘、獨立 run/clock、rate=1、半開30秒範圍、來源 pins；未用系統日期回填展示起點。
- Not verified: Claude複核、catalog凍結、G4、正式RGB／索引／baseline／人工成績。
- Deviations, UNKNOWN items and follow-ups: context尚非可發包；不回改原審查包、舊A/B1、Blender或正式production設定。Refs #113/#93/D80/D81；各核定未完成前不把來源pin當批准。
