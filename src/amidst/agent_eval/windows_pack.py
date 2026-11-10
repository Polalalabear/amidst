"""Self-contained Windows / Colab evaluation pack builder and verifier (WP6 / #515)."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping

_ad = importlib.import_module('amidst.q1q5.agent_decision')

FORBIDDEN_EXACT: frozenset[str] = frozenset(_ad.FORBIDDEN_KEYS) | frozenset({
    'inserted_candidate_ids',
    'scoring_private',
})


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_safe_rel_path(rel: str) -> bool:
    if not isinstance(rel, str) or not rel:
        return False
    if rel.startswith(('/', '\\')) or ':' in rel or '\\' in rel:
        return False
    parts = rel.split('/')
    return all(part and part not in ('.', '..') for part in parts)


def _is_forbidden_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    k = key.lower()
    return k in FORBIDDEN_EXACT or k.startswith('gt_')


def _find_forbidden_keys(obj: Any) -> list[str]:
    bad: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if _is_forbidden_key(k):
                bad.append(str(k))
            bad.extend(_find_forbidden_keys(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            bad.extend(_find_forbidden_keys(item))
    return bad


def _scan_json_or_jsonl_bytes(raw: bytes, label: str) -> list[str]:
    text = raw.decode('utf-8')
    errors: list[str] = []
    if label.endswith('.jsonl'):
        for idx, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f'{label}:{idx}: invalid JSON ({exc})')
                continue
            bad = _find_forbidden_keys(doc)
            if bad:
                errors.append(f'{label}:{idx}: forbidden keys {sorted(set(bad))}')
    elif label.endswith('.json'):
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f'{label}: invalid JSON ({exc})')
        else:
            bad = _find_forbidden_keys(doc)
            if bad:
                errors.append(f'{label}: forbidden keys {sorted(set(bad))}')
    return errors


_VERIFY_PACK_SCRIPT = '''#!/usr/bin/env python3
"""Standalone verifier for Amidst Windows / Colab evaluation pack (WP6 / #515)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

FORBIDDEN_EXACT = frozenset({
    "actor", "actor_id", "gt_actor", "gt_id", "track_id", "raw_track_id",
    "person_id", "target_id", "is_target", "ground_truth", "gt", "depth",
    "3d", "world_xyz", "trajectory", "visibility",
    "inserted_candidate_ids", "scoring_private",
})


def _is_safe_rel_path(rel: str) -> bool:
    if not isinstance(rel, str) or not rel:
        return False
    if rel.startswith(("/", "\\\\")) or ":" in rel or "\\\\" in rel:
        return False
    parts = rel.split("/")
    return all(part and part not in (".", "..") for part in parts)


def _is_forbidden_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    k = key.lower()
    return k in FORBIDDEN_EXACT or k.startswith("gt_")


def _find_forbidden(obj: Any) -> list[str]:
    bad: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if _is_forbidden_key(k):
                bad.append(str(k))
            bad.extend(_find_forbidden(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            bad.extend(_find_forbidden(item))
    return bad


def verify_directory(pack_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest_path = pack_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        return False, ["missing MANIFEST.json"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"invalid MANIFEST.json: {exc}"]

    upload_list = manifest.get("upload_list")
    if not isinstance(upload_list, list) or not upload_list:
        errors.append("MANIFEST.json upload_list must be a non-empty list")
    else:
        for row in upload_list:
            if not isinstance(row, Mapping) or set(row.keys()) != {"relative_path", "sha256"}:
                errors.append(f"invalid upload_list entry: {row!r}")
                continue
            rel = row["relative_path"]
            expected_sha = row["sha256"]
            if not _is_safe_rel_path(rel):
                errors.append(f"unsafe relative_path: {rel!r}")
                continue
            target = pack_dir / rel
            if not target.is_file():
                errors.append(f"missing file from upload_list: {rel}")
                continue
            actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                errors.append(f"sha256 mismatch for {rel}: expected {expected_sha}, got {actual_sha}")

    for path in sorted(pack_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_name = path.relative_to(pack_dir).as_posix()
        if path.suffix == ".json":
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{rel_name}: invalid JSON ({exc})")
                continue
            bad = _find_forbidden(doc)
            if bad:
                errors.append(f"{rel_name}: forbidden keys {sorted(set(bad))}")
        elif path.suffix == ".jsonl":
            for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except Exception as exc:
                    errors.append(f"{rel_name}:{idx}: invalid JSONL ({exc})")
                    continue
                bad = _find_forbidden(doc)
                if bad:
                    errors.append(f"{rel_name}:{idx}: forbidden keys {sorted(set(bad))}")

    return len(errors) == 0, errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    target = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    ok, errors = verify_directory(target)
    if ok:
        print("VALID")
        return 0
    for err in errors:
        print(f"INVALID: {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _render_readme(upload_list: list[dict[str, str]]) -> str:
    upload_lines = '\n'.join(
        f'- `{row["relative_path"]}` - SHA-256: `{row["sha256"]}`'
        for row in upload_list
    )
    return f"""# Amidst Agent 評估自包含實驗包（Windows / Colab L4）

## 工作內容

本實驗包用於執行 Amidst Q1-Q5 Agent 決策評估（Colab L4 開源權重與本地 DRY_RUN 驗證），完全不含真實 Ground Truth、演員識別或私有評分標籤。

| 平台 | 可執行項目 | 不可執行項目 |
| --- | --- | --- |
| Windows / Colab | `python tools/verify_pack.py`、`pytest`、`runner --dry-run`、Colab L4 Ollama 推論 | 真實 GT 抽取、真實 GT 評分、未授權真實 OpenAI API 呼叫 |
| Mac（Claude） | 真實 run 題庫抽取、真實 GT 映射與評分、使用者授權後之 OpenAI 實測 | - |

## 要上傳的檔案

請確認以下檔案清單與 SHA-256 完全一致（可執行 `python tools/verify_pack.py` 自動檢查）：

{upload_lines}

## 操作步驟

1. 在本地解壓或建立實驗包後，先執行驗證腳本確認完整性與無禁止欄位：
   `python tools/verify_pack.py .`（應印出 `VALID` 且返回碼為 `0`）。
2. 若在 Colab 執行開源模型評估，請將本資料夾上傳至 Google Drive 或 Colab 工作區，開啟 `colab_l4.ipynb`，確認 GPU 為 NVIDIA L4 並鎖定 Ollama 模型 digest（`q4_K_M`）。
3. 執行完成後，將產出的 `decisions_*.jsonl`、`recordings_*.jsonl`、`latency_*.json` 與 `run_manifest_*.json` 放入 `RETURN/` 資料夾回傳。

## 不要改

- 請勿修改題庫檔案（`*.jsonl`）、參數檔（`*.json`）或 `MANIFEST.json` 的任何位元組。
- 請勿在實驗包中加入任何包含 `gt_*`、`actor`、`track_id`、`scoring_private` 等禁止鍵值的檔案。
- 請勿在未經授權下啟用 `--live` 呼叫付費 API。
"""


_RETURN_README = """請將實驗回傳產物放置於本資料夾（RETURN/）：
1. decisions_<model>_<stage>.jsonl
2. recordings_<model>_<stage>.jsonl
3. latency_<model>_<stage>.json
4. MANIFEST.json / run_manifest.json

回傳前請於實驗包根目錄執行：
    python tools/verify_pack.py .
確認輸出為 VALID。
"""


def verify_pack(pack_dir: Path | str) -> tuple[bool, list[str]]:
    """Verify a built Windows/Colab pack directory for SHA-256 integrity and forbidden keys."""
    ns: dict[str, Any] = {}
    exec(_VERIFY_PACK_SCRIPT, ns)  # noqa: S102
    verifier = ns['verify_directory']
    return verifier(Path(pack_dir))


def build_pack(out_dir: Path | str, *, files: Mapping[str, Path | str]) -> dict[str, Any]:
    """Build a self-contained Windows/Colab pack with MANIFEST.json, README.md, RETURN/, and verify_pack.py."""
    out_path = Path(out_dir)
    if not files:
        raise ValueError('files mapping must not be empty')

    staged: list[tuple[str, bytes]] = []
    for rel, src in sorted(files.items(), key=lambda kv: kv[0]):
        if not _is_safe_rel_path(rel):
            raise ValueError(f'unsafe relative path in pack: {rel!r}')
        src_path = Path(src)
        raw = src_path.read_bytes()
        errs = _scan_json_or_jsonl_bytes(raw, rel)
        if errs:
            raise _ad.AgentDecisionError('; '.join(errs))
        staged.append((rel, raw))

    out_path.mkdir(parents=True, exist_ok=True)
    upload_list: list[dict[str, str]] = []
    for rel, raw in staged:
        dest = out_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        upload_list.append({
            'relative_path': rel,
            'sha256': _sha256_bytes(raw),
        })

    (out_path / 'RETURN').mkdir(parents=True, exist_ok=True)
    (out_path / 'RETURN' / 'README.txt').write_text(_RETURN_README)

    (out_path / 'tools').mkdir(parents=True, exist_ok=True)
    (out_path / 'tools' / 'verify_pack.py').write_text(_VERIFY_PACK_SCRIPT, encoding='utf-8')

    readme_text = _render_readme(upload_list)
    (out_path / 'README.md').write_text(readme_text)

    manifest: dict[str, Any] = {
        'upload_list': upload_list,
    }
    (out_path / 'MANIFEST.json').write_bytes(_ad.canonical(manifest) + b'\n')
    return manifest
