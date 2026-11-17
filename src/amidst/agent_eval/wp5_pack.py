"""WP5 local-model packs (Colab L4 and Windows): composition, README, zip. Stdlib only; no key, no GT, no media.

The packs carry the WP5 runner and its import closure, the two configs it reads, the response schema, a SYNTHETIC
question file (the real DP1/DP3/DP4/NL bank is UNKNOWN until S1+S2 are final) and a target-specific entry
(notebook for Colab, ``run.py`` for Windows). Latency is only reportable from the Colab L4 pack (D175).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from amidst.agent_eval import windows_pack, wp5_fake

TARGETS = ('colab_l4', 'windows')
PACK_DATE = '20261115'
CODE_FILES = (
    'src/amidst/__init__.py', 'src/amidst/paths.py',
    'src/amidst/agent_eval/__init__.py', 'src/amidst/agent_eval/latency.py', 'src/amidst/agent_eval/runner.py',
    'src/amidst/agent_eval/windows_pack.py', 'src/amidst/agent_eval/wp5.py', 'src/amidst/agent_eval/wp5_fake.py',
    'src/amidst/agent_eval/wp5_runner.py', 'src/amidst/agent_eval/wp5_colab_checks.py',
    'src/amidst/q1q5/agent_decision.py', 'src/amidst/q1q5/agent_providers.py', 'src/amidst/q1q5/agent_wiring.py',
    'src/amidst/q1q5/api_budget.py', 'src/amidst/q1q5/attention_ranking.py', 'src/amidst/q1q5/nl_query_parse.py',
    'src/amidst/q1q5/physical_prediction.py', 'src/amidst/q1q5/q3_rules.py',
)
DATA_FILES = (
    'configs/agent_eval/wp5_v1.json', 'configs/agent_eval/wp5_price_table_v1.json',
    'configs/q1q5/agent_decision_params_v1.json', 'configs/q1q5/agent_decision_params_v1_exploratory.json',
    'docs/contracts/schemas/q-core.agent-decision.v1.schema.json',
    'docs/operations/WP5_COLAB_L4_README.md',
)
NOTEBOOK = 'notebooks/agent_decision/wp5_colab_l4.ipynb'
LOCAL_MODELS = ('qwen2.5:7b-instruct-q4_K_M', 'llama3.1:8b-instruct-q4_K_M')
_SECRET = re.compile(r'sk-[A-Za-z0-9_-]{16,}')
_HOME = re.compile(r'/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\')

WINDOWS_RUN_PY = r'''#!/usr/bin/env python3
"""Windows entry for the WP5 local-model pack. Default is a DRY RUN (0 model calls); --live needs Ollama on this machine.
No API key is read and nothing is sent to OpenAI. Latency from this machine is NOT reportable (no L4, D175)."""
import argparse, hashlib, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS = ["qwen2.5:7b-instruct-q4_K_M", "llama3.1:8b-instruct-q4_K_M"]
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"), OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NUM_PARALLEL="1")


def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, env=ENV, **kw)


def runner(args):
    return sh([sys.executable, "-m", "amidst.agent_eval.wp5_runner", *args], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="pilot", choices=["pilot", "formal", "relaxed_exploration"])
    ap.add_argument("--live", action="store_true", help="run the local models through Ollama (needs ollama installed)")
    ap.add_argument("--skip-types", default="DP4", help="DP4 live calls wait for #532; keep DP4 skipped")
    a = ap.parse_args()
    v = sh([sys.executable, "tools/verify_pack.py", "."], capture_output=True, text=True)
    print(v.stdout.strip()); assert v.returncode == 0 and "VALID" in v.stdout, v.stdout + v.stderr
    out = ROOT / "RETURN" / "wp5"
    r = runner(["--set", a.set, "--arm", "windows", "--skip-types", a.skip_types, "--out", str(out / "dry_run")])
    print(r.stdout, r.stderr); assert r.returncode == 0
    print((out / "dry_run" / "estimate.json").read_text(encoding="utf-8")[:1200])
    if not a.live:
        print("DRY RUN only (0 calls). Re-run with --live to measure."); return 0
    ollama = shutil.which("ollama"); assert ollama, "install Ollama for Windows first"
    version = subprocess.run([ollama, "--version"], capture_output=True, text=True).stdout.strip()
    for m in MODELS:
        subprocess.run([ollama, "pull", m], check=True)
    tags = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
    digests = {x["name"]: x["digest"] for x in tags["models"]}
    (ROOT / "models.txt").write_text("".join(f"{m}@{digests[m]}\n" for m in MODELS), encoding="utf-8")
    from amidst.agent_eval.runner import verify_ollama_models
    check = verify_ollama_models((ROOT / "models.txt").read_text(), tags)
    print(json.dumps(check, ensure_ascii=False, indent=2)); assert check["valid"], check
    failed = False
    for m in MODELS:
        sub = out / a.set / m.replace(":", "_").replace("/", "_")
        r = runner(["--set", a.set, "--arm", "windows", "--models", m, "--skip-types", a.skip_types,
                    "--questions", "data/wp5_questions.jsonl", "--live", "--out", str(sub)])
        print(m, "rc=", r.returncode, r.stderr[-800:]); assert r.returncode in (0, 3), r.stderr
        failed = failed or r.returncode == 3   # 3 = a task type never reached the model (see summary.json 'failures')
        subprocess.run([ollama, "stop", m], check=False)
    env = {"set": a.set, "arm": "windows", "ollama_version": version, "models_txt": (ROOT / "models.txt").read_text(),
           "digests": {m: digests[m] for m in MODELS}, "measure_latency": False, "latency_reportable": False}
    (out / "ENV.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    z = shutil.make_archive(str(ROOT / "RETURN" / f"wp5_{a.set}_windows"), "zip", out)
    print(z, hashlib.sha256(Path(z).read_bytes()).hexdigest())
    if failed:
        print("!! RUN FAILED: at least one task type never reached the model. Do NOT report these results.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _readme(target: str, commit: str):
    colab = target == 'colab_l4'
    zip_name = 'wp5_<set>_colab_l4.zip' if colab else 'wp5_<set>_windows.zip'
    where = 'Colab（選 NVIDIA L4）' if colab else 'Windows（Python 3.12 以上，已安裝 Ollama）'
    ops = (
        "1. 在 Colab 選執行階段 → 變更執行階段類型 → **L4 GPU**。\n"
        "2. 在 Colab 用「檔案 → 上傳筆記本」開 `wp5_colab_l4.ipynb`（和本 zip 放在一起的獨立副本；zip 內 `notebooks/agent_decision/` 也有同一份），再在左側檔案面板把**整個 zip**（`wp5-pack_colab_l4_%s.zip`）上傳到 `/content`。\n"
        "3. 由上而下逐格執行（步驟 0 會自動解壓、切到包根目錄並驗包）。確認 GPU 是 L4（不是 L4 會停）；`SET` 預設 `pilot`；`OLLAMA_VERSION` 預設 `AUTO_LATEST`（取當日最新版並寫進 `ENV.json`）；DP4 先跳過（等 #532）。\n"
        "4. 最後一格會產生 `RETURN/wp5_<set>_colab_l4.zip` 並嘗試下載；沒有自動下載就從檔案面板下載。\n"
        "5. 把下載的 zip 放進 Mac 的 `local/evidence/wp5/<set>/`，用 `shasum -a 256` 記下 SHA-256，回報給協調者。"
    ) % (PACK_DATE,) if colab else (
        "1. 解壓 zip，進入解壓後的資料夾（以下指令都在此資料夾）。\n"
        "2. 先 dry-run（0 次模型呼叫，不需要 Ollama）：`python run.py --set pilot`。要看到 `VALID` 與估算。\n"
        "3. 安裝 Ollama for Windows 並確認 `ollama --version`；再執行 `python run.py --set pilot --live`（會 pull 兩個 q4_K_M 模型、寫入 digest、一次跑一個模型）。\n"
        "4. 完成後 `RETURN/wp5_<set>_windows.zip` 就是要回傳的檔案。此機器沒有 L4，**延遲不可當正式結果**（`ENV.json` 記 `latency_reportable: false`）。\n"
        "5. 把 zip 放進 Mac 的 `local/evidence/wp5/<set>/`，記下 SHA-256，回報給協調者。")

    def render(upload_list: list[dict[str, str]]) -> str:
        lines = '\n'.join(f'- `{r["relative_path"]}` - SHA-256: `{r["sha256"]}`' for r in upload_list)
        return f"""# Amidst WP5 本機模型包（{where}）

來源 commit：`{commit}`（main）。不需要任何 API key，不呼叫 OpenAI，不花錢。

## 工作內容

用 Ollama 在本機跑兩個 q4_K_M 模型（`{LOCAL_MODELS[0]}`、`{LOCAL_MODELS[1]}`），一次一個，跑 WP5 題組（pilot：DP1／DP3／NL 各 4 題 × 6 輪；DP4 即時呼叫等 #532，先跳過），量每次呼叫的延遲、token、逾時與備援。主要結果是延遲和費用（本機費用恆為 0）；準確度只記錄、評分在 Mac。{'' if colab else '此機器沒有 L4，延遲只作功能驗證，不報告。'}

題目檔 `data/wp5_questions.jsonl` 是**合成題**（`SYNTHETIC`，由 `wp5_fake.synthetic_rows` 產生，不含 GT、身分或影像）；真題庫 UNKNOWN（S1+S2 最終題數未定），拿到後會另發新包。合成題的延遲只反映同等長度提示的速度。

## 要上傳的檔案

整個 zip 一次上傳，不要拆。以下清單與 SHA-256 可由 `python tools/verify_pack.py .` 自動檢查（應印 `VALID`）：

{lines}

## 操作步驟

{ops}

## 要提交項目（RETURN/）

只放 `RETURN/{zip_name}`，內容：每個模型的 `calls.jsonl`、`summary.json`、`summary.md`、`MANIFEST.json`，以及 `ENV.json`（GPU、Ollama 版本、`models.txt` 與 digest）。詳見 `RETURN/README.txt`。

## 不要改

- 不要修改任何檔案的位元組（`MANIFEST.json` 會比對）。
- 不要加入 `gt_*`、`actor`、`track_id`、`scoring_private` 等欄位或檔案。
- 不要設定 `OPENAI_API_KEY`，也不要加 `--approved-usd`；本包只跑本機模型。
"""
    ret = f"""請把實驗產物放在本資料夾（RETURN/），指定回傳檔：

    {zip_name}

內容：
  <模型>/calls.jsonl、summary.json、summary.md、MANIFEST.json（每個模型一個資料夾）
  ENV.json（GPU／Ollama 版本／models.txt／digest）

回傳前在包根目錄執行 `python tools/verify_pack.py RETURN/{zip_name}`，要印 VALID。
把 zip 放進 Mac 的 local/evidence/wp5/<set>/ 並記下 SHA-256。
"""
    return render, ret


def _forbidden_text(path: Path) -> list[str]:
    bad = []
    if path.suffix not in ('.py', '.json', '.jsonl', '.md', '.ipynb', '.txt'):
        return bad
    text = path.read_text(encoding='utf-8')
    if _SECRET.search(text):
        bad.append(f'{path}: looks like an API key')
    if _HOME.search(text):
        bad.append(f'{path}: absolute home path')
    return bad


def build_wp5_pack(out_dir: Path | str, *, repo_root: Path | str, target: str, commit: str, per_type: int = 40) -> dict[str, Any]:
    """Build one pack directory plus ``<out_dir>.zip`` (deterministic). Returns paths, SHA-256 and sizes."""
    if target not in TARGETS:
        raise ValueError(f'target must be one of {TARGETS}')
    root, out = Path(repo_root), Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        files: dict[str, Path] = {rel: root / rel for rel in CODE_FILES + DATA_FILES}
        rows = wp5_fake.synthetic_rows(per_type)
        q = tmp_path / 'wp5_questions.jsonl'
        q.write_bytes(b''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode() + b'\n' for r in rows))
        files['data/wp5_questions.jsonl'] = q
        info = tmp_path / 'PACK_INFO.json'
        info.write_text(json.dumps({'pack': f'wp5-{target}', 'date': PACK_DATE, 'source_commit': commit, 'question_class': 'SYNTHETIC',
                                    'questions_per_type': per_type, 'latency_reportable': target == 'colab_l4'}, indent=2) + '\n', encoding='utf-8')
        files['PACK_INFO.json'] = info
        if target == 'colab_l4':
            files[NOTEBOOK] = root / NOTEBOOK
        else:
            run = tmp_path / 'run.py'
            run.write_text(WINDOWS_RUN_PY, encoding='utf-8')
            files['run.py'] = run
        problems = [p for src in files.values() for p in _forbidden_text(src)]
        if problems:
            raise ValueError('; '.join(problems))
        render, ret = _readme(target, commit)
        windows_pack.build_pack(out, files=files, readme_renderer=render, return_readme=ret)
    problems = [p for f in out.rglob('*') if f.is_file() for p in _forbidden_text(f)]
    if problems:
        raise ValueError('; '.join(problems))
    ok, errors = windows_pack.verify_pack(out)
    if not ok:
        raise ValueError('; '.join(errors))
    zip_path = out.with_suffix('.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(p for p in out.rglob('*') if p.is_file()):
            zi = zipfile.ZipInfo(f'{out.name}/{f.relative_to(out).as_posix()}', date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, f.read_bytes())
    n_files = sum(1 for p in out.rglob('*') if p.is_file())
    return {'target': target, 'dir': str(out), 'zip': str(zip_path), 'zip_sha256': _sha(zip_path.read_bytes()),
            'zip_bytes': zip_path.stat().st_size, 'n_files': n_files}
