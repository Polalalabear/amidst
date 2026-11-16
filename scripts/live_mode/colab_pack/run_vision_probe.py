"""Adjudication probe for local vision models on Ollama (Colab). Standard library only.

For every model: pull, record the digest, warm up, check `ollama ps` while a request is in flight, then ask every
question twice (image: one combined picture; text: pixel-derived features only). Writes hardware.json, ENV.json,
<model>/calls.jsonl, summary.json and REPORT.md under --out. The pack has no ground truth: accuracy is scored later
on the Mac. No API key, no paid call.

Colab limits this script is written around:
  - a session can disconnect at any time: every answer is appended to calls.jsonl at once and a re-run skips what is
    already there (resume); hardware.json is rewritten on every run and ENV.json keeps one entry per model;
  - the GPU is not guaranteed: without a GPU the run refuses to start (--allow-cpu overrides); the GPU name and memory
    are recorded, and a model that Ollama splits between CPU and GPU is flagged in the report;
  - disk and downloads: free disk is checked before each pull, pulls are retried, and --rm-after deletes each model
    when it is done so several models never sit on disk together;
  - the first request loads the model (can take minutes): the warm-up has its own long timeout and is discarded;
  - long silent cells look hung: progress is printed every few questions.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

SYSTEM = ("A camera system tracks one person (the target). It sees camera pixels only. Identity is never confirmed: "
          "you only judge which candidate best matches the target's appearance and movement. "
          "Answer 0 when no candidate matches. Reply in JSON.")
NUM_PREDICT = 200
NUM_CTX = 4096          # set explicitly: an older default (2048) would cut off the image tokens
MIN_FREE_GIB = 15       # needed before pulling one ~6-9 GiB model
KEEP_ALIVE = "10m"


def sh(cmd: list[str], timeout: float = 60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def hardware() -> dict:
    gpu = sh(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader"])
    cpu = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip(); break
    except OSError:
        pass
    mem_kb = 0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem_kb = int(line.split()[1]); break
    except OSError:
        pass
    du = shutil.disk_usage(".")
    parts = [p.strip() for p in gpu.splitlines()[0].split(",")] if gpu else []
    return {"gpu_name": parts[0] if parts else None, "gpu_memory_total": parts[1] if len(parts) > 1 else None,
            "gpu_memory_used_at_start": parts[2] if len(parts) > 2 else None, "gpu_driver": parts[3] if len(parts) > 3 else None,
            "gpu_count": len(gpu.splitlines()) if gpu else 0, "cpu_model": cpu or platform.processor() or None, "cpu_logical_cores": os.cpu_count(),
            "ram_total_gib": round(mem_kb / 1048576, 1) if mem_kb else None, "disk_free_gib": round(du.free / 2**30, 1),
            "os": platform.platform(), "python": platform.python_version(), "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def post(endpoint: str, path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(endpoint + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def schema(k: int) -> dict:
    return {"type": "object", "required": ["choice", "reason"],
            "properties": {"choice": {"type": "integer", "enum": list(range(0, k + 1))}, "reason": {"type": "string"}}}


def col(c: dict) -> str:
    return f"hue {c['h_deg']} deg, saturation {c['s']}, brightness {c['v']}"


def message(q: dict, root: Path, variant: str) -> dict:
    k = q["n_candidates"]
    ask = f"Which numbered person (1-{k}) is the target? 0 if none. Give the reason in Traditional Chinese, at most 40 characters."
    if variant == "image":
        img = base64.b64encode((root / q["combined"]).read_bytes()).decode()
        return {"role": "user", "content": "Left panel: the target when the system first locked on. Right panel: a camera frame now, "
                f"candidates are numbered in yellow boxes. {ask}", "images": [img]}
    r = q["reference_features"]
    lines = [f"Target at first lock: upper body {col(r['upper'])}; lower body {col(r['lower'])}; box height {r['box_height_px']} px.",
             f"Seconds since the target was last matched: {q['seconds_since_last_match']}.", f"Candidates in camera {q['camera']}:"]
    for c in q["candidates"]:
        lines.append(f"{c['number']}: upper body {col(c['upper'])}; lower body {col(c['lower'])}; box height {c['box_height_px']} px; "
                     f"detector score {c['detector_score']}; {c['metres_from_last_estimate']} m from the last estimated position; "
                     f"speed needed {c['speed_needed_m_s']} m/s (walking is about 1.2, running about 2.5).")
    return {"role": "user", "content": "\n".join(lines) + "\n" + ask}


def ask(endpoint: str, model: str, q: dict, root: Path, variant: str, timeout: float) -> dict:
    body = {"model": model, "stream": False, "format": schema(q["n_candidates"]), "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "seed": 7, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
            "messages": [{"role": "system", "content": SYSTEM}, message(q, root, variant)]}
    row = {"qid": q["qid"], "variant": variant, "model": model, "n_candidates": q["n_candidates"]}
    t0 = time.perf_counter()
    try:
        d = post(endpoint, "/api/chat", body, timeout)
    except urllib.error.HTTPError as exc:
        row.update(latency_ms=(time.perf_counter() - t0) * 1000, valid=False, error=f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}")
        return row
    except Exception as exc:  # noqa: BLE001 - recorded per row
        row.update(latency_ms=(time.perf_counter() - t0) * 1000, valid=False, error=f"{type(exc).__name__}: {str(exc)[:200]}")
        return row
    ns = lambda k: (d.get(k) or 0) / 1e6  # noqa: E731
    text = (d.get("message") or {}).get("content") or ""
    row.update(latency_ms=(time.perf_counter() - t0) * 1000, load_ms=ns("load_duration"), prompt_eval_ms=ns("prompt_eval_duration"), eval_ms=ns("eval_duration"),
               prompt_tokens=d.get("prompt_eval_count"), completion_tokens=d.get("eval_count"), done_reason=d.get("done_reason"), raw_head=text[:160])
    try:
        a = json.loads(text)
        row.update(choice=a.get("choice"), reason=a.get("reason"),
                   valid=isinstance(a.get("choice"), int) and not isinstance(a.get("choice"), bool) and 0 <= a["choice"] <= q["n_candidates"])
    except (TypeError, ValueError, AttributeError):
        row.update(choice=None, reason=None, valid=False)
    return row


def pct(v: list, p: float):
    v = sorted(v)
    if not v:
        return None
    i = (len(v) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo))


def summarize(rows: list[dict]) -> list[dict]:
    out = []
    for key in sorted({(r["model"], r["variant"]) for r in rows}):
        cs = [r for r in rows if (r["model"], r["variant"]) == key]
        ok = [r for r in cs if r.get("valid")]
        lat = [r["latency_ms"] for r in ok]
        tps = [r["completion_tokens"] / (r["eval_ms"] / 1000) for r in ok if r.get("eval_ms") and r.get("completion_tokens")]
        hist: dict = {}
        for r in ok:
            hist[str(r["choice"])] = hist.get(str(r["choice"]), 0) + 1
        mean = lambda k: round(sum(r[k] for r in ok if r.get(k) is not None) / max(1, sum(1 for r in ok if r.get(k) is not None)))  # noqa: E731
        out.append({"model": key[0], "variant": key[1], "calls": len(cs), "valid": len(ok), "valid_rate": round(len(ok) / len(cs), 3) if cs else None,
                    "errors": sum(1 for r in cs if r.get("error")), "latency_ms_valid_p50": pct(lat, 0.5), "latency_ms_valid_p90": pct(lat, 0.9),
                    "latency_ms_valid_max": round(max(lat)) if lat else None, "prompt_tokens_mean": mean("prompt_tokens") if ok else None,
                    "completion_tokens_mean": mean("completion_tokens") if ok else None, "prompt_eval_ms_mean": mean("prompt_eval_ms") if ok else None,
                    "eval_ms_mean": mean("eval_ms") if ok else None, "output_tokens_per_s": round(sum(tps) / len(tps), 1) if tps else None, "answers": hist})
    return out


def report(hw: dict, env: dict, summary: list[dict]) -> str:
    L = ["# 影像裁決測試：Colab 本機視覺模型", "", f"- 產生時間（UTC）：{hw['captured_at_utc']}", f"- 題數：{env['questions']}；每題跑 {', '.join(env['variants'])}",
         "- 這份報告沒有正確率：題目包不含標準答案，正確率回到 Mac 上評分。", "", "## 硬體規格", "", "| 項目 | 值 |", "| --- | --- |"]
    for k, name in [("gpu_name", "GPU"), ("gpu_memory_total", "GPU 記憶體"), ("gpu_driver", "GPU 驅動"), ("gpu_count", "GPU 數量"), ("cpu_model", "CPU"),
                    ("cpu_logical_cores", "CPU 邏輯核心"), ("ram_total_gib", "RAM (GiB)"), ("disk_free_gib", "磁碟可用 (GiB)"), ("os", "作業系統"), ("python", "Python")]:
        L.append(f"| {name} | {hw.get(k)} |")
    L += [f"| Ollama | {env.get('ollama_version')} |", "", "## 模型", "", "| 模型 | digest | 載入時 `ollama ps` | 載入後 GPU 記憶體 |", "| --- | --- | --- | --- |"]
    for m in env["models"]:
        L.append(f"| {m['name']} | {str(m.get('digest'))[:19]} | {m.get('pull_error') or m.get('ollama_ps_processor') or '沒抓到'} | {m.get('gpu_memory_used_loaded') or '沒抓到'} |")
    L += ["", "## 結果", "", "延遲只算格式合法的回答。", "", "| 模型 | 輸入 | 呼叫 | 合法率 | 延遲 p50 (ms) | 延遲 p90 (ms) | 輸入 token | 輸出 token | 輸出 token/秒 | 答案分布 |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for s in summary:
        L.append(f"| {s['model']} | {'看圖' if s['variant'] == 'image' else '文字特徵'} | {s['calls']} | {s['valid_rate']} | {s['latency_ms_valid_p50']} | {s['latency_ms_valid_p90']} | "
                 f"{s['prompt_tokens_mean']} | {s['completion_tokens_mean']} | {s['output_tokens_per_s']} | {json.dumps(s['answers'], ensure_ascii=False)} |")
    warn = [f"- {m['name']}：`ollama ps` 不是 100% GPU（{m.get('ollama_ps_processor') or '沒抓到'}），延遲不能當 GPU 上的結果。" for m in env["models"] if "100% GPU" not in str(m.get("ollama_ps_processor"))]
    warn += [f"- {s['model']}（{s['variant']}）：合法率 {s['valid_rate']}，低於 0.9。" for s in summary if (s["valid_rate"] or 0) < 0.9]
    if not hw.get("gpu_name"):
        warn.append("- 沒有偵測到 GPU。")
    elif "L4" not in hw["gpu_name"]:
        warn.append(f"- GPU 是 {hw['gpu_name']}，不是 L4。文字模型的比較（D175）是在 L4 上做的，這份延遲不能直接和它比。")
    if (hw.get("ram_total_gib") or 99) < 12:
        warn.append(f"- RAM 只有 {hw['ram_total_gib']} GiB，載入模型時可能不夠。")
    warn += [f"- {s['model']}（{s['variant']}）：只完成 {s['calls']} 次呼叫，少於題數，可能是連線中斷；重新執行同一格會接著跑。" for s in summary if s["calls"] < env["questions"]]
    L += ["", "## 要注意的地方", ""] + (warn or ["- 沒有。"])
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--questions", default="data")
    ap.add_argument("--out", default="RETURN/adjudication")
    ap.add_argument("--variants", default="image,text")
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout-s", type=float, default=120)
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--allow-cpu", action="store_true", help="run even when no GPU is found (very slow; latency is not a GPU result)")
    ap.add_argument("--rm-after", action="store_true", help="delete each model after its run to free disk")
    a = ap.parse_args()
    root, out = Path(a.questions), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    qs = [json.loads(x) for x in (root / "questions.jsonl").read_text().splitlines() if x.strip()]
    if a.limit:
        qs = qs[: a.limit]
    variants = a.variants.split(",")
    hw = hardware()
    (out / "hardware.json").write_text(json.dumps(hw, indent=1, ensure_ascii=False))
    print("hardware:", json.dumps(hw, ensure_ascii=False), flush=True)
    if not hw["gpu_name"] and not a.allow_cpu:
        print("REFUSED: no GPU found. In Colab choose Runtime > Change runtime type > a GPU (L4 recommended), then run again.")
        return 2
    prev = {}
    if (out / "ENV.json").is_file():  # resume: keep what earlier runs recorded about each model
        prev = {m["name"]: m for m in json.loads((out / "ENV.json").read_text()).get("models", [])}
    env = {"ollama_version": sh(["ollama", "--version"]) or None, "questions": len(qs), "variants": variants, "num_predict": NUM_PREDICT,
           "num_ctx": NUM_CTX, "models": []}
    rows_all: list[dict] = []
    for model in a.models.split(","):
        info = dict(prev.get(model) or {"name": model})
        mdir = out / model.replace(":", "_").replace("/", "_"); mdir.mkdir(parents=True, exist_ok=True)
        done = {}
        if (mdir / "calls.jsonl").is_file():  # resume after a disconnect: rows with an answer or a model reply are kept
            for line in (mdir / "calls.jsonl").read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    if not r.get("error"):
                        done[(r["qid"], r["variant"])] = r
        todo = [(q, v) for q in qs for v in variants if (q["qid"], v) not in done]
        rows_all.extend(done.values())
        if not todo:
            print(model, "already complete, skipped", flush=True)
            env["models"].append(info); continue
        free = shutil.disk_usage(".").free / 2**30
        if not a.no_pull:
            if free < MIN_FREE_GIB:
                info["pull_error"] = f"only {free:.1f} GiB free, need {MIN_FREE_GIB}"
                print(model, "SKIPPED:", info["pull_error"], flush=True)
                env["models"].append(info); continue
            for attempt in range(3):  # downloads on Colab sometimes stall
                if subprocess.run(["ollama", "pull", model], check=False).returncode == 0:
                    info.pop("pull_error", None); break
                info["pull_error"] = f"ollama pull failed ({attempt + 1}/3)"; time.sleep(10)
            if info.get("pull_error"):
                print(model, "SKIPPED:", info["pull_error"], flush=True)
                env["models"].append(info); continue
        try:
            tags = json.loads(urllib.request.urlopen(a.endpoint + "/api/tags", timeout=10).read())
            info["digest"] = next((m.get("digest") for m in tags.get("models", []) if m.get("name") == model), None)
        except Exception:  # noqa: BLE001
            info["digest"] = None
        try:  # warm-up, discarded
            post(a.endpoint, "/api/chat", {"model": model, "stream": False, "keep_alive": KEEP_ALIVE, "options": {"num_predict": 8},
                                           "messages": [{"role": "user", "content": "ping"}]}, 600)
        except Exception as exc:  # noqa: BLE001
            info["warmup_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        seen: list[str] = []

        def watch():  # read `ollama ps` while the first real request is running
            for _ in range(40):
                o = sh(["ollama", "ps"], 10)
                line = next((x for x in o.splitlines()[1:] if x.split() and x.split()[0] == model), "")
                if line:
                    seen.append(line); return
                time.sleep(0.25)
        th = threading.Thread(target=watch, daemon=True); th.start()
        kept = [json.dumps(r, ensure_ascii=False) for r in done.values()]
        (mdir / "calls.jsonl").write_text("".join(x + "\n" for x in kept), encoding="utf-8")  # drop earlier error rows, they are retried
        t_model = time.time()
        with open(mdir / "calls.jsonl", "a", encoding="utf-8") as fh:
            for n, (q, v) in enumerate(todo, 1):
                r = ask(a.endpoint, model, q, root, v, a.timeout_s)
                rows_all.append(r); fh.write(json.dumps(r, ensure_ascii=False) + "\n"); fh.flush(); os.fsync(fh.fileno())
                if n % 6 == 0 or n == len(todo):
                    print(f"  {model}: {n}/{len(todo)} ({time.time() - t_model:.0f} s)", flush=True)
        th.join(timeout=2)
        info["ollama_ps_line"] = seen[0] if seen else None
        if seen:  # e.g. "100% GPU", "100% CPU" or "23%/77% CPU/GPU" (model does not fit in GPU memory)
            import re
            m = re.search(r"\d+%(?:/\d+%)?\s+(?:CPU/GPU|GPU|CPU)", seen[0])
            info["ollama_ps_processor"] = m.group(0) if m else seen[0]
        elif "ollama_ps_processor" not in info:
            info["ollama_ps_processor"] = None
        g = sh(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"])
        info["gpu_memory_used_loaded"] = g.splitlines()[0] if g else None
        sh(["ollama", "stop", model], 60)
        if a.rm_after:
            sh(["ollama", "rm", model], 120)
        env["models"].append(info)
        (out / "ENV.json").write_text(json.dumps(env, indent=1, ensure_ascii=False))  # written after every model, in case the session drops
        print(model, "done:", sum(1 for r in rows_all if r["model"] == model and r.get("valid")), "valid of", sum(1 for r in rows_all if r["model"] == model))
    summary = summarize(rows_all)
    (out / "ENV.json").write_text(json.dumps(env, indent=1, ensure_ascii=False))
    (out / "summary.json").write_text(json.dumps({"hardware": hw, "env": env, "rows": summary}, indent=1, ensure_ascii=False))
    (out / "REPORT.md").write_text(report(hw, env, summary), encoding="utf-8")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
