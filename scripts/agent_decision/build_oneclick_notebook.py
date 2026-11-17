#!/usr/bin/env python3
"""Build the single-file Colab notebook for WP5: the Colab L4 pack zip embedded (base64) in cell 1, steps 1-7 taken from
``notebooks/agent_decision/wp5_colab_l4.ipynb``. Output: ``wp5_colab_oneclick.ipynb`` and a deterministic ``.zip``.

Order: build the pack first (``scripts/agent_decision/build_wp5_packs.py``), then run this with that pack's zip.
No key, no GT, no media. Existing outputs are renamed ``*.v<N>`` (not overwritten)."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK = REPO / 'notebooks/agent_decision/wp5_colab_l4.ipynb'

INTRO = '''# Amidst WP5 延遲組（Colab L4，本機模型）— 單檔一鍵版

**三步，不需要任何 API key、不呼叫 OpenAI、不花錢：**

1. **選 L4**：選單「執行階段 → 變更執行階段類型 → L4 GPU」→ 儲存。（不是 L4 會在步驟 1 停下並說明。）
2. **上傳**：把這一個 `wp5_colab_oneclick.ipynb` 上傳到 Colab（檔案 → 上傳筆記本）。資料包已經嵌在第一格裡，不用另外上傳 zip。
3. **全部執行**：選單「執行階段 → 全部執行」，等它跑完（約數十分鐘，視題組而定）。最後一格會自動下載 `wp5_pilot_colab_l4.zip`，並印出要把它放到哪裡。

流程：解開內嵌資料包並驗 SHA-256 與 `verify_pack`（`VALID`）→ 確認 L4 → 設定（`SET="pilot"`、`SKIP_TYPES="DP4"`）→ 安裝 Ollama → pull 兩個 q4_K_M 模型並驗 digest → dry-run（0 次呼叫）→ 一次一個模型：暖機、`ollama ps` 要 100% GPU、送一題 DP1 確認有模型回應、跑題組、卸載 → 檢查各題型 fallback 比例 → 打包並下載。題目檔只含請求，沒有 Ground Truth；評分在 Mac。

**v2 修正（2026-11-15）：** v1 的 DP1／DP3 全部沒有呼叫到模型（`PROVIDER_UNAVAILABLE`，約 35 ms 就退回規則），v1 結果作廢。送給 Ollama 的 `format` schema 現在是自包含的；筆記本多了 GPU 與模型回應檢查，紅字＝這個結果不能用。

**關於 Colab 的「沒使用到 GPU」提示：** 它只看這支筆記本的 Python 程序，而它不用 CUDA；真正用 GPU 的是另一個 `ollama serve` 程序。看筆記本印出的 `ollama ps`（要顯示 `100% GPU`）和 `nvidia-smi` 才準。'''


def _lines(text: str) -> list[str]:
    parts = text.split('\n')
    return [p + '\n' for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def embedded_cell(zip_bytes: bytes, pack_name: str) -> str:
    b64 = base64.b64encode(zip_bytes).decode('ascii')
    chunks = '\n'.join(f"    '{b64[i:i + 100]}'" for i in range(0, len(b64), 100))
    return f'''# 步驟 0：把內嵌資料包寫到 /content、驗 SHA-256、解壓、驗包（要得到 VALID）。
import base64, hashlib, os, subprocess, sys, zipfile
from pathlib import Path
EXPECTED_SHA256 = "{hashlib.sha256(zip_bytes).hexdigest()}"
PACK_NAME = "{pack_name}"
PACK_B64 = (
{chunks}
)
base = Path("/content") if Path("/content").is_dir() else Path.cwd()
base.mkdir(parents=True, exist_ok=True)
zip_path = base / (PACK_NAME + ".zip")
zip_path.write_bytes(base64.b64decode("".join(PACK_B64)))
got = hashlib.sha256(zip_path.read_bytes()).hexdigest()
print("pack zip:", zip_path, zip_path.stat().st_size, "bytes", got)
assert got == EXPECTED_SHA256, "SHA-256 mismatch: the embedded pack is corrupted; re-upload this notebook"
zipfile.ZipFile(zip_path).extractall(base)
os.chdir(base / PACK_NAME)
print("pack root:", os.getcwd())
sys.path.insert(0, str(Path("src").resolve()))
os.environ["PYTHONPATH"] = str(Path("src").resolve()) + os.pathsep + os.environ.get("PYTHONPATH", "")
v = subprocess.run([sys.executable, "tools/verify_pack.py", "."], capture_output=True, text=True)
print(v.stdout.strip()); assert v.returncode == 0 and "VALID" in v.stdout, v.stdout + v.stderr
'''


def build_notebook(pack_zip: Path, notebook: Path = NOTEBOOK) -> dict:
    pack_name = re.sub(r'\.zip$', '', pack_zip.name)
    base = json.loads(notebook.read_text(encoding='utf-8'))
    cells = base['cells']
    step0 = {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [],
             'source': _lines(embedded_cell(pack_zip.read_bytes(), pack_name))}
    intro = {'cell_type': 'markdown', 'metadata': {}, 'source': _lines(INTRO)}
    return {'cells': [intro, step0, *cells[2:]],
            'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                         'language_info': {'name': 'python'}, 'accelerator': 'GPU', 'colab': {'provenance': []}},
            'nbformat': 4, 'nbformat_minor': 5}


def _keep_old(path: Path) -> Path | None:
    if not path.exists():
        return None
    n = 1
    while path.with_name(f'{path.name}.v{n}').exists():
        n += 1
    dest = path.with_name(f'{path.name}.v{n}')
    path.rename(dest)
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack-zip', required=True, help='wp5-pack_colab_l4_<date>.zip from build_wp5_packs.py')
    ap.add_argument('--out', required=True, help='output folder (LOCAL), e.g. local/data/wp5-packs-20261115/oneclick')
    ap.add_argument('--notebook', default=str(NOTEBOOK))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    nb_path, zip_path = out / 'wp5_colab_oneclick.ipynb', out / 'wp5_colab_oneclick.zip'
    old = [_keep_old(nb_path), _keep_old(zip_path)]
    nb = build_notebook(Path(a.pack_zip), Path(a.notebook))
    nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    zi = zipfile.ZipInfo(nb_path.name, date_time=(1980, 1, 1, 0, 0, 0))
    zi.external_attr = 0o644 << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr(zi, nb_path.read_bytes())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    print(json.dumps({'notebook': str(nb_path.resolve()), 'notebook_sha256': sha(nb_path), 'notebook_bytes': nb_path.stat().st_size,
                      'zip': str(zip_path.resolve()), 'zip_sha256': sha(zip_path), 'zip_bytes': zip_path.stat().st_size,
                      'pack_zip_sha256': sha(Path(a.pack_zip)), 'kept_old': [str(o) for o in old if o]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
