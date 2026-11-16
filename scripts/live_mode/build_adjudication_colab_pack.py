"""Build the Colab pack for the local vision-model adjudication probe.

python scripts/live_mode/build_adjudication_colab_pack.py --questions <dir with questions.jsonl, img/> --out <dir> [--date YYYYMMDD]

The pack holds: the questions (no ground truth), one combined picture per question (reference crop on the left, the
numbered camera frame on the right, because some local vision models accept a single image), the runner, a notebook,
a verifier and a README. The zip is deterministic. Needs Pillow for the combined pictures. The pack is LOCAL (the
pictures are rendered frames); only this builder and the files under colab_pack/ are in git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent / "colab_pack"
MODELS = ["qwen2.5vl:7b-q4_K_M", "qwen3-vl:8b-instruct-q4_K_M", "llama3.2-vision:11b-instruct-q4_K_M"]
FORBIDDEN = ("answers_private", "candidate_actors", "actor_id")


def combined(ref: Path, frame: Path, dst: Path) -> None:
    f = Image.open(frame).convert("RGB")
    r = Image.open(ref).convert("RGB")
    panel = 240
    s = min((panel - 20) / r.width, (f.height - 50) / r.height)
    r = r.resize((max(1, int(r.width * s)), max(1, int(r.height * s))))
    out = Image.new("RGB", (panel + f.width, f.height), (255, 255, 255))
    out.paste(r, ((panel - r.width) // 2, 40 + (f.height - 50 - r.height) // 2))
    out.paste(f, (panel, 0))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, panel - 1, 30], fill=(0, 0, 0)); d.text((8, 9), "REFERENCE: the target", fill=(255, 230, 0))
    d.rectangle([panel, 0, panel + 150, 22], fill=(0, 0, 0)); d.text((panel + 8, 5), "CAMERA FRAME NOW", fill=(255, 230, 0))
    out.save(dst, "JPEG", quality=90)


def cell(kind: str, src: str) -> dict:
    c = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def notebook(date: str) -> dict:
    cells = [
        cell("markdown", f"""# Amidst 影像裁決測試（Colab，本機視覺模型）

這本筆記本在 Colab 的 GPU 上用 Ollama 跑看得懂圖的開源模型，回答「畫面裡哪個編號的人是目標」。**不需要 API key，不呼叫 OpenAI，不花錢。**

**執行前**：執行階段 → 變更執行階段類型 → 硬體加速器選 **L4 GPU**（沒有 L4 時 T4 也能跑，報告會標明）。建議開「高 RAM」。

**流程**：上傳測試包 → 檢查硬體 → 安裝 Ollama → 一次跑一個模型 → 顯示硬體規格和結果 → 下載結果 zip。全部跑完大約 30–50 分鐘，大部分時間在下載模型。

**Colab 的幾個限制**：
- 連線可能中斷。中斷後重新連線，從步驟 0 依序重跑即可，已經答過的題目會跳過（如果執行階段被回收，檔案會消失，就要從頭來）。
- 畫面可能出現「沒有使用 GPU」的提示。那個提示只看這本筆記本的 Python 程序，真正用 GPU 的是另一個 `ollama serve` 程序。以報告裡的 `ollama ps` 欄位為準。
- 長時間沒有操作會被斷線。跑的時候讓這個分頁保持開著。

題目包裡沒有標準答案，所以這裡的報告沒有正確率；正確率回到 Mac 上評分。"""),
        cell("code", f"""# 步驟 0：上傳並解開測試包（adjudication-pack_colab_{date}.zip），然後驗包。
import glob, os, subprocess, sys, zipfile
from pathlib import Path
NAME = "adjudication-pack_colab_{date}"
if Path("/content").is_dir():
    os.chdir("/content")            # 重跑這一格時回到固定位置，避免路徑一層一層疊進去
if not Path(NAME, "MANIFEST.json").is_file():
    if not glob.glob(NAME + ".zip"):
        from google.colab import files   # 只在 Colab 有；會跳出選檔視窗
        files.upload()
    zipfile.ZipFile(NAME + ".zip").extractall(".")
os.chdir(NAME)
v = subprocess.run([sys.executable, "tools/verify_pack.py", "."], capture_output=True, text=True)
print(os.getcwd()); print(v.stdout.strip()); assert v.returncode == 0, v.stdout + v.stderr"""),
        cell("code", """# 步驟 1：看這次分到的硬體。沒有 GPU 就停下來，回到上面改執行階段類型。
import json, subprocess
print(subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout or "找不到 nvidia-smi：這個執行階段沒有 GPU")
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
assert gpu, "沒有 GPU：執行階段 → 變更執行階段類型 → 選 L4 GPU，然後從步驟 0 重跑"
print("GPU:", gpu)
if "L4" not in gpu:
    print("\\033[1;31m注意：不是 L4。可以繼續跑，但延遲不能和先前 L4 上的文字模型結果直接比較。\\033[0m")"""),
        cell("code", f"""# 步驟 2：設定。MODELS 一次跑一個；想少跑就刪掉幾個。RM_AFTER=True 會在每個模型跑完後刪掉它，省磁碟。
MODELS = {json.dumps(MODELS)}
VARIANTS = "image,text"      # image：看圖；text：只看從畫面量出來的數字（對照組）
RM_AFTER = True
OLLAMA_VERSION = "AUTO_LATEST"   # 也可以手動填版本號，例如 0.40.16；實際版本會寫進報告
LIMIT = 0                    # 0 = 全部 36 題；先試跑可以填 3"""),
        cell("code", """# 步驟 3：安裝 Ollama 並在背景啟動。Colab 沒有 systemd，所以自己啟動 ollama serve。
import json, os, subprocess, time, urllib.request
subprocess.run("apt-get -qq update && apt-get -qq install -y zstd pciutils lshw > /dev/null", shell=True)   # 新版 Ollama 的安裝檔需要 zstd
if OLLAMA_VERSION == "AUTO_LATEST":
    try:
        OLLAMA_VERSION = json.loads(urllib.request.urlopen("https://api.github.com/repos/ollama/ollama/releases/latest", timeout=20).read())["tag_name"].lstrip("v")
    except Exception as exc:      # GitHub API 偶爾會限流；裝預設的最新版
        print("查不到最新版本號，改裝安裝腳本的預設版本：", exc); OLLAMA_VERSION = ""
def up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2); return True
    except Exception:
        return False
if not up():                      # 重跑這一格時不會重複安裝、重複啟動
    cmd = "curl -fsSL https://ollama.com/install.sh | " + (f"OLLAMA_VERSION={OLLAMA_VERSION} " if OLLAMA_VERSION else "") + "sh"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True); print(r.stdout[-600:], r.stderr[-600:])
    env = dict(os.environ, OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NUM_PARALLEL="1")
    subprocess.Popen(["ollama", "serve"], stdout=open("ollama_serve.log", "a"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    for _ in range(90):
        if up(): break
        time.sleep(1)
assert up(), "ollama serve 沒有起來，看 ollama_serve.log 最後幾行：\\n" + "".join(open("ollama_serve.log").readlines()[-15:])
print(subprocess.run(["ollama", "--version"], capture_output=True, text=True).stdout.strip())"""),
        cell("code", """# 步驟 4：跑測試。每個模型：下載 → 暖機 → 36 題 × 2 種輸入 → 卸載。進度會一直印出來。
# 中斷後重跑這一格會接著做。看到「沒有使用 GPU」的提示不用理會，以最後報告的 ollama ps 欄位為準。
import subprocess, sys
cmd = [sys.executable, "-u", "run_vision_probe.py", "--models", ",".join(MODELS), "--variants", VARIANTS, "--questions", "data", "--out", "RETURN/adjudication"]
if RM_AFTER: cmd.append("--rm-after")
if LIMIT: cmd += ["--limit", str(LIMIT)]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in p.stdout:
    if not line.startswith(("pulling ", "verifying ", "writing ")): print(line, end="")
assert p.wait() == 0, "測試沒有正常結束，看上面的訊息" """),
        cell("code", """# 步驟 5：顯示硬體規格和分析結果（同一份內容存在 RETURN/adjudication/REPORT.md）。
from pathlib import Path
from IPython.display import Markdown, display
display(Markdown(Path("RETURN/adjudication/REPORT.md").read_text(encoding="utf-8")))"""),
        cell("code", f"""# 步驟 6：打包並下載。瀏覽器擋下載的話，從左邊的檔案面板對 zip 按右鍵下載。
import hashlib, shutil
from pathlib import Path
z = shutil.make_archive("RETURN/adjudication_colab_{date}", "zip", "RETURN/adjudication")
print(z, Path(z).stat().st_size, "bytes", "SHA-256", hashlib.sha256(Path(z).read_bytes()).hexdigest())
try:
    from google.colab import files
    files.download(z)
except Exception as exc:
    print("自動下載沒有成功：", exc)"""),
    ]
    return {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "L4", "machine_shape": "hm", "provenance": []},
                                         "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


README = """# 影像裁決測試包（Colab，本機視覺模型，{date}）

## 工作內容
在 Colab 的 GPU 上用 Ollama 跑三個看得懂圖的開源模型，回答 {n} 題「畫面裡哪個編號的人是目標」。每題跑兩次：看圖，以及只看從畫面量出來的數字。
不需要 API key，不呼叫 OpenAI，不花錢。包裡沒有標準答案，正確率回到 Mac 上評分。

預設模型（都是 q4_K_M）：
{models}

## 要上傳的檔案
1. `adjudication-pack_colab_{date}.zip`（就是這一包）
2. 筆記本 `adjudication_vision_colab.ipynb`（在包裡，也另外放了一份在包的旁邊）

## 操作步驟
1. 在 Colab 開啟 `adjudication_vision_colab.ipynb`。
2. 執行階段 → 變更執行階段類型 → **L4 GPU**，建議開高 RAM。沒有 L4 時 T4 也能跑，報告會標明。
3. 從上到下依序執行每一格。步驟 0 會跳出選檔視窗，選這個 zip。
4. 步驟 4 最久（下載三個模型各 6–9 GB，加上 {calls} 次推論），大約 30–50 分鐘。讓分頁保持開著。
5. 步驟 5 會顯示硬體規格和結果。步驟 6 下載 `adjudication_colab_{date}.zip`。

連線中斷：重新連線後從步驟 0 依序重跑，答過的題目會跳過。執行階段被回收的話檔案會消失，要從頭來。

## 要提交項目
把步驟 6 下載的 `adjudication_colab_{date}.zip` 放到 Mac 的 `local/evidence/live-mode-adjudication-20261116/colab/`。裡面有：
- `REPORT.md`：硬體規格和結果表
- `hardware.json`、`ENV.json`：GPU、CPU、RAM、磁碟、Ollama 版本、模型 digest、`ollama ps`
- `summary.json`、每個模型的 `calls.jsonl`

## 不要改
`data/`、`run_vision_probe.py`、`tools/`、`MANIFEST.json`。要少跑模型或先試跑，只改筆記本步驟 2 的設定。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default="20261116")
    a = ap.parse_args()
    src, name = Path(a.questions), f"adjudication-pack_colab_{a.date}"
    root = Path(a.out) / name
    (root / "data" / "img").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(exist_ok=True); (root / "RETURN").mkdir(exist_ok=True)
    qs = []
    for line in (src / "questions.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        rel = f"img/{q['qid']}_combined.jpg"
        combined(src / q["reference"], src / q["frame"], root / "data" / rel)
        q = {k: v for k, v in q.items() if k not in ("frame", "reference")}
        q["combined"] = rel
        qs.append(q)
    text = "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in qs)
    assert not any(f in text for f in FORBIDDEN)
    (root / "data" / "questions.jsonl").write_text(text, encoding="utf-8")
    (root / "run_vision_probe.py").write_bytes((HERE / "run_vision_probe.py").read_bytes())
    (root / "tools" / "verify_pack.py").write_bytes((HERE / "verify_pack.py").read_bytes())
    nb = json.dumps(notebook(a.date), ensure_ascii=False, indent=1)
    (root / "adjudication_vision_colab.ipynb").write_text(nb, encoding="utf-8")
    (Path(a.out) / "adjudication_vision_colab.ipynb").write_text(nb, encoding="utf-8")
    (root / "RETURN" / "README.txt").write_text(f"Colab writes results here. Bring back: adjudication_colab_{a.date}.zip\n", encoding="utf-8")
    (root / "README.md").write_text(README.format(date=a.date, n=len(qs), calls=len(qs) * 2 * len(MODELS), models="\n".join(f"- `{m}`" for m in MODELS)), encoding="utf-8")
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    man = {"pack": name, "questions": len(qs), "models": MODELS, "files": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (root / "MANIFEST.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    zpath = Path(a.out) / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:  # fixed timestamps and order -> same bytes for the same input
        for p in sorted(root.rglob("*")):
            if p.is_file():
                zi = zipfile.ZipInfo(f"{name}/{p.relative_to(root)}", date_time=(2026, 11, 16, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = 0o644 << 16
                z.writestr(zi, p.read_bytes())
    print(json.dumps({"zip": str(zpath), "bytes": zpath.stat().st_size, "sha256": hashlib.sha256(zpath.read_bytes()).hexdigest(), "files": len(man["files"]) + 1, "questions": len(qs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
