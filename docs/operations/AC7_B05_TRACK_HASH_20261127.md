# AC7 B-05 追蹤雜湊診斷（#773）

2026-11-27。比較 [#764 的 8785 走查](https://github.com/Polalalabear/amidst/pull/764) 和 gate r5 的規則回應。兩組收據的程式碼版本都是 `5727fc9ab6a5e16d5ad6897a0a9e450da81fa7b1`。B-05 是 P1 v4 合成工程場景，追蹤身分為 `UNCONFIRMED`，物理通行為 `UNKNOWN`。

## 8785 重複請求

對 `http://127.0.0.1:8785/api/q_bootstrap` 的連線被拒絕（curl exit 7、HTTP 000），交付前複查同樣結果。現場同一 session 的重跑標為 `UNKNOWN`。#764 的 B-05 首次追蹤及清空時間欄位後的查詢留下兩份逐位相同的 JSON 檔。首次請求的原始 body 未留存，因此無法把歷史檔案當作同一原始請求的現場重複驗證。gate r5 在 900 與 1300 px 高度的 B-05 首次追蹤檔也逐位相同。

兩邊可核對原始 body 的清空時間欄位請求都是 `POST /api/q_core_track`，去掉授權用 `session_ref` 後完全相同。canonical SHA-256 為 `479e0f7a4933566de18a518f1a09f673dbf55518859380d5310e42094d83aabd`。查詢為 person、未指定顏色、空區域篩選，`Asia/Taipei` 的 2026-11-01 13:00:00 至 13:00:08（來源時間 0–8,000,000 µs）。省略 `switch_mode` 即 `RULE_ONLY`，也沒有 `manual_seed`。首筆請求的測試流程與腳本 SHA 相同，兩邊都以來源範圍 0–8,000,000 µs 作答。

## 第一個分歧與傳遞方式

- **8785 收據**。#764 記載正式 `serve_demo_integration.py --auto-root-8cam … --port 8785`，bootstrap 顯示 Agent 不可用。B-05 回應的參數集雜湊等於 P1 v4 registry 原始 pin。當時的完整程序環境和逾時環境變數原值為 `UNKNOWN`，現場無法讀取有效 bootstrap。
- **gate r5 收據**。port 62860 由 `harness/server.py` 直接呼叫 `Demo`，以 `configuration()` 讀預設 config，再指定 8CAM safe bundle、獨立 state 與 queue，設定 `AMIDST_RECORDED_AGENT=openai` 並將 Agent transport 換成 exact-SHA replay。完整繼承環境未保存。有效參數集的 canonical hash 精確符合沒有額外 timeout 覆寫的 D313 路徑。
- 兩邊 B-05 都從 `configs/demo_integration_local.json` 預設的 P1 v4 bundle 取得參數。pin 的 [`P1.__init__`](../../src/amidst/q1q5/p1_workbench.py) 讀 `BUNDLE.json` 指向的 registry，由 [`from_environment`](../../src/amidst/q1q5/api.py) 依 `parameter_ref` 載入 `data/registry/parameter.json`。bundle manifest SHA-256 為 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`，原始 parameter 檔案 SHA-256 為 `b5acee2c00fe1bb4f33223414de887b63992aa52ec12205bc1a9fab968737a06`。
- 第一個可重現的分歧在 [`openai_gateway.ensure_agent_parameters`](../../src/amidst/q1q5/openai_gateway.py)。gate 在啟動時把 `agent_call_timeout_ms` 從 2,000 改為 8,000 ms，把 `agent_total_budget_ms` 從 5,000 改為 24,000 ms，兩列的來源標成 D313 並重算整份 parameter set。B-05 原有其餘 Agent 列。參數集核准狀態兩邊都是 `APPROVED`，兩組規則回應均無 `agent` 欄位。
- [`Demo.call`](../../scripts/serve_demo_integration.py) 將 B-05 送進 [`core_track`](../../src/amidst/q1q5/service_core_track.py)。[`LocalLinker`](../../src/amidst/q1q5/linker.py) 從 run、clock、camera、起始觀測 ID 與**整份**參數集雜湊生成 `local:…` 識別碼。兩邊的 20 筆 sightings 對應 4 個本地識別碼，識別碼在 sightings 與 association audit 內同步改變。兩份回應的欄位級差異只出現在這些引用、參數雜湊及最後的 `output_sha256`。觀測 ID、`single_view`、`multi_view`、時間與狀態欄位逐項相同。加上 `display_estimate` 後，`Demo.with_estimate` 對整份回應重算雜湊，排除頂層 `output_sha256` 與 `stats`。

| B-05 來源 | `parameter_set_sha256` | 首個 `track_ref` | `output_sha256` |
| --- | --- | --- | --- |
| 8785 AC-720 封存 | `3d3067f500fc533c4d1b26812f7be45c8c56299b7bb02b5872de8a4358938e4e` | `local:b3855c53d9e7f870` | `fb2dc77e76e247c6b240be935b4e172c16a754a0257190248088fab0e5b49533` |
| gate r5 replay 服務的規則回應 | `c1d63e2aa5b59433b1076fb6303d04e007af7d96ecc1cf5ac8bdcac3aba0ee7c` | `local:62b265eba361c1bf` | `b2b86626d556b45201f759f06e4efd1ad2b9e2e054f67e1cbf3989db9f4fd563` |

兩邊 B-05 的 run 是 `ENGINEERING_DYNAMIC_RUN_20261025`，索引版本 `detidx:rSYN:ENGINEERING_DYNAMIC_RUN_20261025:22f855debd033dee`，索引內容 SHA-256 `302655b01273a72dd29356d2b6f888bd2f2dcf79266c05c8bdbc73aad31f0e5c`，偵測記錄檔 SHA-256 `816c261d4a3c4d243a6ce2a718a00690585763b68e928c8c0b3534182875ed2b`。時鐘 `ENGINEERING_DYNAMIC_CLOCK` 的 mapping version 為 `SYNTHETIC`，內容 SHA-256 為 `e04cbf9233e8c32605a401789126a17718846e6e169a94316db00e553367e629`。

A4-1、B4-1 的完整 JSON 各自相等，輸出 SHA-256 分別為 `bcc36032b41a8de05b10b86c280431257047f42e3b6f7560d5d0e8fc3d3cc28e`、`bc921cfe90a197c95141b05fb111fa34dba546b99b4021d6fd1bd79e9137ef43`。這兩筆原始視角採 `Demo.cross`，候選引用在初始化時由 pin 的 cross-camera job 產生，規則回應採 job 的 `self.cross_params`。這條回應路徑沒有把稍後可被 Agent wiring 重新封存的 `QRun` 參數雜湊放入回應。

**預期值依啟動設定判定。** Agent-off 的 8785 規則基線是 `fb2dc77e…`。gate r5 在 Agent-on 的 D313 設定下執行同一規則請求，預期 `b2b86626…`。用同一來源、請求及有效參數集可逐欄重現各自的回應，沒有確認需修正的追蹤程式 bug。本紀錄不把離線重算計入 AC7 正式驗收。

## 離線重算

從 pin 對應的程式碼 checkout 執行下列 Python。以支援專案相依套件的 Python 3.12，透過 `AMIDST_LOCAL` 指向包含 `data/` 及 `evidence/` 的既有 LOCAL 根目錄。用 `AMIDST_LOCAL=<LOCAL根目錄> PYTHONPATH="$PWD/src:$PWD/scripts" python -B <儲存下列程式的檔案>`。程式直接讀已釘選的 registry 與偵測記錄，呼叫 B-05 規則端點的後端方法。用同一個暫時 session 值各呼叫 3 次，逐欄校對完整 JSON。無 HTTP server、外連、子程序、原始影像讀取或模型呼叫，費用為 0。

```python
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from amidst.q1q5.api import from_environment
from amidst.q1q5.openai_gateway import ensure_agent_parameters
from amidst.q1q5.store import canonical_hash
from serve_demo_integration import Demo, P1_PIN

root = Path(os.environ["AMIDST_LOCAL"]).resolve()
bundle = root / "data/demo-owned-v1/data/p1-v4"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())



manifest = bundle / "MANIFEST.json"
assert sha(manifest) == P1_PIN
registry = bundle / "data/registry/registry.json"
assert sha(registry) == read(manifest)["files"]["data/registry/registry.json"]["sha256"]
os.chdir(registry.parent)  # frozen registry declares a relative data_root of "."
os.environ.update(AMIDST_Q1Q5_REGISTRY=str(registry), AMIDST_Q1Q5_REGISTRY_SHA256=sha(registry))
for key in ("AMIDST_Q1Q5_OLLAMA_RUNTIME", "AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256"):
    os.environ.pop(key, None)



def offline(event, args):
    if event in ("socket.connect", "subprocess.Popen"):
        raise RuntimeError(event)


sys.addaudithook(offline)
api = from_environment(None, bundle / "app")
key, base = next(iter(api.runs.items()))
token = "offline-diagnostic"
demo = Demo.__new__(Demo)  # only the read-only B-05 call path, no server or startup state
demo.core_track_keys = {key}
demo.sessions = {token: {key[0]}}
demo.positions = {}
demo.calibrations = {}
request_hashes = set()
for folder, run in (("ac-720-20261127", base),
                    ("gate-pin-20261127-r5", ensure_agent_parameters(base))):
    evidence = root / "evidence" / folder / "real-1300"
    result = read(evidence / "browser-results.json")
    payload = next(r["blankPayload"].copy() for r in result["results"] if r["name"] == "B-05-blind")
    payload.pop("session_ref")
    assert "switch_mode" not in payload and "manual_seed" not in payload
    request_hashes.add(canonical_hash(payload))
    payload["session_ref"] = token
    demo.api = SimpleNamespace(runs={key: run})
    expected = read(evidence / "B-05-track-response.json")
    assert read(evidence / "B-05-blind-response.json") == expected
    for _ in range(3):
        assert demo.call("q_core_track", payload) == expected
    print(folder, run.bindings.parameter_sha256, expected["output_sha256"], "3/3")
assert len(request_hashes) == 1
print("request (without session)", request_hashes.pop())
```

若 8785 由其擁有者恢復後再驗，先 GET `/api/q_bootstrap` 確認場景、資料與有效參數雜湊，再以 `/api/session` 建立一個僅在記憶體中的 demo session。使用上述 B-05 body，指定 `RULE_ONLY`，用同一 session 重複 POST `/api/q_core_track` 三次，記錄各次 HTTP 狀態、`parameter_set_sha256`、`track_ref` 與 `output_sha256`。已驗證現行 pin 的 `Demo.call` 只有 `AGENT_SEQUENTIAL` 會建立追蹤 decider。8785 的實際 3 次 HTTP 結果為 `UNKNOWN`。

## LOCAL 證據

下列 manifest SHA-256 含既有封存。這次只校對診斷使用的 16 個 metadata 檔。規則 JSON 可按上面的步驟重算，歷史瀏覽器報告及啟動收據須保留原檔。

| LOCAL 資料夾 | 本次校對的檔數與大小 | `SHA256SUMS` 的 SHA-256 |
| --- | --- | --- |
| `local/evidence/ac-720-20261127/` | 5 檔，469,948 bytes | `5e53b7d9171764f7c59a75af5a3e1b0a770bf84fc5e67bbb01f7102c3e5ebb04` |
| `local/evidence/gate-pin-20261127-r5/` | 11 檔，778,872 bytes | `b668d04735826dc8310e6fbfdf73a7b29e6dc38c54cc17980834f56fa29ea6aa` |

兩組都校對 `real-1300/browser-results.json`、三個 `*-track-response.json` 與 `B-05-blind-response.json`。gate 另校對 `harness/server.py`、`exact-replay/{bootstrap,server,server-cleanup}.json`、`RESULT.txt` 與 `real-900/B-05-track-response.json`。
