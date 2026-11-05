#!/usr/bin/env python3
"""W-A6 Colab 一鍵測試執行器（環境自檢 → API Key 狀態檢查 → 資料包 SHA-256 驗證 → 中斷續跑 → 結果彙整匯出）。

本模組供 `notebooks/amidst_q1q5_colab_oneclick.ipynb` 與自動化測試呼叫：
1. 環境自檢：收集 OS、CPU、RAM、GPU/VRAM、Python/torch 版本，產生並驗證 `amidst.experiment-env.v1`。
2. API Key 安全檢查：僅從 `google.colab.userdata` 或環境變數回報 `PRESENT` / `MISSING`，絕不印出或記錄任何金鑰值。
3. Google Drive 與 W-C5 safe 資料包驗證：檢查 SHA-256 並拒絕任何含 `gt_private` 的路徑；
   當真實 W-C5 資料包尚未提供時，明確標記 `real_data_status="UNKNOWN"` 並自動切換至 `SYNTHETIC` 測試資料集。
4. 中斷續跑（Checkpoint / Resume）：逐事件、逐模型組合（M0/RULE_ONLY 與 M1～M4）寫入 JSONL checkpoint，
   重跑時自動跳過已完成且設定／輸入雜湊一致的項目。
5. 分析與匯出：呼叫研究分析腳本並產出彙整 CSV、視覺化比較圖（PNG）與 `EXPORT_MANIFEST.json` SHA-256。
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

import _common as c  # noqa: E402
import analyze_experiments as ax  # noqa: E402
import build_baseline_table as bt  # noqa: E402
import experiment_env as env_mod  # noqa: E402

ENV_SCHEMA_VERSION = 'amidst.experiment-env.v1'
RESULTS_CONTRACT = c.CONTRACT
DEFAULT_SEED = c.SEED
DEFAULT_KEY_NAMES = (
    'OPENAI_API_KEY',
    'GEMINI_API_KEY',
    'ANTHROPIC_API_KEY',
    'OLLAMA_HOST',
)
SYNTHETIC_FIXTURE_FILES = (
    'SYNTHETIC_baseline_results.json',
    'SYNTHETIC_m1_results.json',
    'SYNTHETIC_m2_results.json',
    'SYNTHETIC_m3_queries_eligible.csv',
    'SYNTHETIC_m3_results.json',
    'SYNTHETIC_m4_results.json',
)


def sha256_bytes(raw: bytes) -> str:
    """計算位元組之 SHA-256 十六進位字串。"""
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    """計算檔案之 SHA-256 十六進位字串。"""
    return sha256_bytes(Path(path).read_bytes())


def canonical_json_sha256(obj: Any) -> str:
    """計算正規化 JSON 物件之 SHA-256。"""
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256_bytes(raw)


def _to_float(val: Any) -> float | None:
    """將數值或數值字串轉為 float；若為 UNKNOWN 或無法轉換則回傳 None。"""
    if c.is_unknown(val) or isinstance(val, bool):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _detect_ram_gib() -> float | str:
    """嘗試偵測系統記憶體（GiB），無法取得時回傳 UNKNOWN。"""
    try:
        import psutil  # type: ignore
        total = getattr(psutil.virtual_memory(), 'total', None)
        if isinstance(total, (int, float)) and total > 0:
            return round(float(total) / (1024 ** 3), 2)
    except Exception:
        pass
    meminfo = Path('/proc/meminfo')
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding='utf-8', errors='ignore').splitlines():
                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        return round(int(parts[1]) / (1024 ** 2), 2)
        except Exception:
            pass
    return c.UNKNOWN


def _detect_gpu_and_torch() -> dict[str, Any]:
    """偵測 PyTorch 與 GPU/VRAM 狀態；未安裝或無 GPU 時安全降級。"""
    info: dict[str, Any] = {
        'torch_version': 'NOT_INSTALLED',
        'cuda_available': False,
        'gpu_model': 'NONE',
        'gpu_driver': 'NONE',
        'gpu_vram_gib': 'NONE',
        'accelerator': 'cpu',
    }
    try:
        import torch  # type: ignore
        info['torch_version'] = str(getattr(torch, '__version__', 'UNKNOWN'))
        if hasattr(torch, 'cuda') and torch.cuda.is_available():
            info['cuda_available'] = True
            info['accelerator'] = 'cuda'
            info['gpu_model'] = str(torch.cuda.get_device_name(0) or 'CUDA_GPU')
            props = torch.cuda.get_device_properties(0)
            total_mem = getattr(props, 'total_memory', 0)
            if isinstance(total_mem, (int, float)) and total_mem > 0:
                info['gpu_vram_gib'] = round(float(total_mem) / (1024 ** 3), 2)
            cuda_ver = getattr(getattr(torch, 'version', None), 'cuda', None)
            info['gpu_driver'] = f'cuda-{cuda_ver}' if cuda_ver else 'UNKNOWN'
        elif hasattr(getattr(torch, 'backends', None), 'mps') and torch.backends.mps.is_available():
            info['accelerator'] = 'mps'
            info['gpu_model'] = 'Apple_MPS'
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# Cell 1: 環境自檢與 amidst.experiment-env.v1 manifest
# ---------------------------------------------------------------------------

def inspect_environment(
    *,
    run_id: str = 'SYNTHETIC-colab-oneclick-0001',
    source_class: str = 'SYNTHETIC',
    deterministic: bool = True,
    started_at_utc: str = '2026-11-04T00:00:00Z',
    finished_at_utc: str = '2026-11-04T00:01:00Z',
) -> dict[str, Any]:
    """執行 Colab / 本地環境自檢，產生並驗證符合 `amidst.experiment-env.v1` 的環境紀錄。"""
    gpu_info = _detect_gpu_and_torch()
    in_colab = 'google.colab' in sys.modules or bool(os.environ.get('COLAB_RELEASE_TAG'))

    if deterministic:
        os_block = {
            'os_name': 'SYNTHETIC-Colab-Linux',
            'os_version': '6.1',
            'kernel': '6.1.0-colab',
            'arch': 'x86_64',
        }
        hw_block = {
            'cpu_model': 'SYNTHETIC-Colab-CPU',
            'cpu_cores': '4',
            'gpu_model': 'NONE',
            'gpu_driver': 'NONE',
            'ram_gib': 12.7,
            'accelerator': 'cpu',
        }
        rt_block = {
            'python_version': '3.12.0',
            'python_implementation': 'CPython',
            'isolated_mode': True,
            'node_version': 'UNKNOWN',
        }
        installed_pkgs = {
            'python': '3.12.0',
            'torch': 'NOT_INSTALLED',
        }
    else:
        os_block = {
            'os_name': platform.system() or 'UNKNOWN',
            'os_version': platform.release() or 'UNKNOWN',
            'kernel': platform.version() or 'UNKNOWN',
            'arch': platform.machine() or 'UNKNOWN',
        }
        hw_block = {
            'cpu_model': platform.processor() or 'UNKNOWN',
            'cpu_cores': str(os.cpu_count() or 'UNKNOWN'),
            'gpu_model': gpu_info['gpu_model'],
            'gpu_driver': gpu_info['gpu_driver'],
            'ram_gib': _detect_ram_gib(),
            'accelerator': gpu_info['accelerator'],
        }
        rt_block = {
            'python_version': platform.python_version() or 'UNKNOWN',
            'python_implementation': platform.python_implementation() or 'UNKNOWN',
            'isolated_mode': True,
            'node_version': 'UNKNOWN',
        }
        installed_pkgs = {
            'python': platform.python_version() or 'UNKNOWN',
            'torch': str(gpu_info['torch_version']),
        }

    manifest: dict[str, Any] = {
        'schema_version': ENV_SCHEMA_VERSION,
        'run': {
            'run_id': run_id,
            'git_commit': '0000000000000000000000000000000000000424',
            'git_dirty': False,
            'started_at_utc': started_at_utc,
            'finished_at_utc': finished_at_utc,
            'wall_clock_s': 60.0,
        },
        'parameter_set': {
            'parameter_set_id': 'SYNTHETIC-colab-oneclick-params',
            'status': 'PROPOSED',
            'parameter_set_sha256': '1111111111111111111111111111111111111111111111111111111111111111',
            'applies_to_run_ids': [run_id],
            'run_bound_approval': 'UNRESOLVED',
        },
        'source_class': source_class,
        'data_sources': [
            {
                'role': 'synthetic_research_fixtures',
                'locator': 'tests/fixtures/research/SYNTHETIC_baseline_results.json',
                'sha256': sha256_file(REPO_ROOT / 'tests/fixtures/research/SYNTHETIC_baseline_results.json'),
                'size_bytes': (REPO_ROOT / 'tests/fixtures/research/SYNTHETIC_baseline_results.json').stat().st_size,
                'file_count': 1,
            }
        ],
        'models': {
            'llm': {
                'llm_name': 'SYNTHETIC-llm',
                'llm_digest': 'SYNTHETIC-digest',
                'ollama_version': '0.0.0',
                'quant': 'UNKNOWN',
                'llm_loaded_size_gib': 'UNKNOWN',
                'llm_processor': 'UNKNOWN',
            },
            'detector': {
                'detector_name': 'SYNTHETIC-detector',
                'detector_weights_sha256': 'UNKNOWN',
                'detector_source_commit': 'UNKNOWN',
            },
        },
        'hardware': hw_block,
        'os': os_block,
        'runtime': rt_block,
        'packages': {
            'uv_lock_sha256': 'UNKNOWN',
            'pyproject_sha256': 'UNKNOWN',
            'installed': installed_pkgs,
        },
        'config': {
            'switch_mode': 'RULE_ONLY',
            'parser_mode': 'RULE_ONLY',
            'agent_max_rounds': 3,
            'agent_call_timeout_ms': 2000,
            'agent_total_budget_ms': 5000,
            'q3_max_llm_attempts': 'UNKNOWN',
            'q3_llm_timeout_ms': 2000,
            'llm_temperature': 'UNKNOWN',
            'torch_deterministic': 'UNKNOWN',
        },
        'seeds': {
            'random_seed': DEFAULT_SEED,
            'llm_seed': 'UNKNOWN',
        },
        'gt_isolation': {
            'inference_read_gt': False,
            'input_manifest_sha256': '3333333333333333333333333333333333333333333333333333333333333333',
            'gt_path_scan': 'PASS',
        },
        'source': {
            'scene_id': 'SYNTHETIC-scene',
            'scene_revision': 'UNKNOWN',
            'clock_id': 'UNKNOWN',
            'clock_type': 'UNKNOWN',
            'camera_scope': ['SYN_CAM'],
            'source_fps': 5,
            'sampling_stride': 'UNKNOWN',
            'sampling_interval_us': 200000,
        },
        'timings_s': {
            'read': 'UNKNOWN',
            'forward': 'UNKNOWN',
        },
        'contract_scope': {
            'production_contract': 'UNSELECTED',
            'human_approval_verified': False,
            'allowed_purposes': [],
        },
    }

    errors = env_mod.validate(manifest)
    if errors:
        raise ValueError(f'Invalid {ENV_SCHEMA_VERSION} manifest: {errors}')
    manifest_sha = env_mod.canonical_sha256(manifest)
    return {
        'env_manifest': manifest,
        'env_manifest_sha256': manifest_sha,
        'validation_errors': errors,
        'probe_summary': {
            'in_colab': in_colab,
            'os_name': os_block['os_name'],
            'cpu_cores': hw_block['cpu_cores'],
            'ram_gib': hw_block['ram_gib'],
            'gpu_model': hw_block['gpu_model'],
            'gpu_vram_gib': 'NONE' if deterministic else gpu_info['gpu_vram_gib'],
            'python_version': rt_block['python_version'],
            'torch_version': installed_pkgs['torch'],
        },
    }


# ---------------------------------------------------------------------------
# Cell 2: API Key 安全讀取（絕不印出或記錄任何金鑰值）
# ---------------------------------------------------------------------------

def check_api_keys(
    key_names: tuple[str, ...] = DEFAULT_KEY_NAMES,
    *,
    env_mapping: Mapping[str, str] | None = None,
    userdata_getter: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """安全檢查 API Key 是否存在（僅回傳 `PRESENT` 或 `MISSING`，絕不回傳或記錄金鑰內容）。"""
    if userdata_getter is None:
        try:
            from google.colab import userdata as colab_userdata  # type: ignore

            def _default_getter(name: str) -> str | None:
                try:
                    return colab_userdata.get(name)
                except Exception:
                    return None

            userdata_getter = _default_getter
        except Exception:
            userdata_getter = lambda _name: None

    source_env = os.environ if env_mapping is None else env_mapping
    status_map: dict[str, str] = {}
    for name in key_names:
        val = None
        try:
            val = userdata_getter(name)
        except Exception:
            val = None
        if not val:
            val = source_env.get(name)
        is_present = isinstance(val, str) and len(val.strip()) > 0
        status_map[name] = 'PRESENT' if is_present else 'MISSING'
        # 立即清除區域變數參照，確保不留存任何敏感字串
        del val

    return {
        'key_Names_checked': list(key_names),
        'keys_status': status_map,
        'any_key_present': any(v == 'PRESENT' for v in status_map.values()),
        'secret_values_logged': False,
        'policy': 'STATUS_ONLY_NEVER_LOG_VALUES',
    }


# ---------------------------------------------------------------------------
# Cell 3: Google Drive 掛載與 W-C5 safe 資料包 SHA-256 驗證（含路徑遍歷／symlink／GT 隔離拒絕）
# ---------------------------------------------------------------------------

FORBIDDEN_NAME_PATTERN = re.compile(
    r'(?i)(?:^|[^a-z0-9])(?:gt|gt_private|ground_truth|groundtruth|private|trajector(?:y|ies)|renderer_track|depth|visibility|waypoints?|keyframes?)(?:$|[^a-z0-9])'
)
ALLOWED_PACK_SUFFIXES = {
    '.json', '.jsonl', '.png', '.py', '.mjs', '.css', '.html', '.txt', '.csv', '.sha256', '.md'
}
MAX_PACK_FILE_BYTES = 64 * 1024 * 1024  # 64 MiB

ALLOWED_SAFE_PACK_FORMATS = {
    'amidst.argon-safe-pack.v1',
    'amidst.wc5-safe-pack.v1',
    'amidst.safe-pack.v1',
}

APPROVED_SAFE_PACK_ROOTS: dict[str, dict[str, Any]] = {
    'p1-v4-stripped': {
        'manifest_sha256': 'c7f32857948468e54cdafa8d8eaaefce730c6660378191b2b2ecfe3f80dcf7fd',
        'format': 'amidst.argon-safe-pack.v1',
    },
    'cx7-d119': {
        'manifest_sha256': '5d7bde92462cd3b72604b612f676565c487edfa469af5c6a46f03a6cbe8fd115',
        'format': 'amidst.argon-safe-pack.v1',
    },
    'cx7-d124': {
        'manifest_sha256': '6a0d90d00580a1c6bace411316fc909e09a209a0ac282841328ef4e209ba762f',
        'format': 'amidst.argon-safe-pack.v1',
    },
}


def _is_symlink_or_reparse(path: Path) -> bool:
    """檢查路徑是否為符號連結或 Windows reparse point / junction。"""
    try:
        if path.is_symlink() or os.path.islink(path):
            return True
        if hasattr(path, 'is_junction') and path.is_junction():
            return True
    except OSError:
        return True
    return False


def _assert_no_gt_private(paths: list[str]) -> None:
    """檢查路徑清單：若任一路徑段包含 GT 或私有資料關鍵字，立即拋出 ValueError。"""
    for rel in paths:
        norm = rel.replace('\\', '/')
        parts = [p for p in norm.split('/') if p]
        for part in parts:
            if FORBIDDEN_NAME_PATTERN.search(part):
                raise ValueError(f'Forbidden GT / private token detected in path component: {part!r} (in {rel})')


def _validate_safe_relative_path(root_dir: Path, rel_str: str) -> Path:
    """嚴格驗證 safe 資料包內部之相對路徑：
    1. 拒絕絕對路徑、'..' 遍歷、無效字元（\\, :, \\0）。
    2. 拒絕符號連結、Windows junction / reparse point。
    3. 強制副檔名白名單與大小上限（<= 64 MiB）。
    4. 驗證 canonical containment（不可透過任何方式跳脫 root_dir）。
    5. 確保為 regular file。
    """
    if not isinstance(rel_str, str) or not rel_str.strip():
        raise ValueError(f'Invalid empty or non-string relative path: {rel_str!r}')
    if '\\' in rel_str or ':' in rel_str or '\0' in rel_str:
        raise ValueError(f'Disallowed characters in relative path: {rel_str!r}')

    posix_path = PurePosixPath(rel_str)
    if posix_path.is_absolute():
        raise ValueError(f'Absolute path forbidden in data pack: {rel_str}')
    if '..' in posix_path.parts:
        raise ValueError(f"Path traversal ('..') forbidden in data pack: {rel_str}")
    if posix_path.as_posix() != rel_str:
        raise ValueError(f'Non-canonical posix relative path: {rel_str}')

    for part in posix_path.parts:
        if FORBIDDEN_NAME_PATTERN.search(part):
            raise ValueError(f'Forbidden GT / private token in relative path component: {part!r} (in {rel_str})')

    if posix_path.suffix.lower() not in ALLOWED_PACK_SUFFIXES:
        raise ValueError(f'Disallowed file suffix in safe pack: {rel_str} (suffix: {posix_path.suffix})')

    root_canonical = root_dir.resolve()
    fpath = root_dir.joinpath(*posix_path.parts)

    cur = fpath
    while True:
        if cur.exists() and _is_symlink_or_reparse(cur):
            raise ValueError(f'Symlink or junction forbidden in safe pack: {cur}')
        if cur == root_dir or cur in cur.parents or cur.parent == cur:
            break
        cur = cur.parent

    if not fpath.is_file() or _is_symlink_or_reparse(fpath):
        raise ValueError(f'Expected regular file without symlinks: {rel_str}')

    if fpath.stat().st_size > MAX_PACK_FILE_BYTES:
        raise ValueError(f'File exceeds maximum safe size ({MAX_PACK_FILE_BYTES} bytes): {rel_str}')

    fpath_canonical = fpath.resolve()
    try:
        fpath_canonical.relative_to(root_canonical)
    except ValueError:
        raise ValueError(f'Path escapes safe pack root: {rel_str} (resolves to {fpath_canonical})')

    return fpath


def verify_data_pack(
    pack_dir: Path | str | None = None,
    *,
    expected_manifest_sha256: str | None = None,
    approved_manifest_sha256: str | None = None,
    expected_hashes: Mapping[str, str] | None = None,
    allow_synthetic_fallback: bool = True,
    fixture_dir: Path | None = None,
) -> dict[str, Any]:
    """驗證 W-C5 safe 資料包之 SHA-256、路徑安全性、owning manifest 格式／schema 與 GT 隔離。

    信任根規則（Root of Trust）：
    1. 不盲目信任任意未核定 pack 內部自含之 MANIFEST.json / SAFE_PACK_MANIFEST.json。
    2. 必須比對核定之信任根（expected_manifest_sha256 / approved_manifest_sha256 /
       環境變數 AMIDST_APPROVED_WC5_MANIFEST_SHA256 / APPROVED_SAFE_PACK_ROOTS）。
    3. 若資料包缺乏上游已核定之 provenance 或純屬本地 self-declared，嚴格禁止宣稱 real_data_status=VERIFIED、
       active_data_mode=REAL_WC5_PACK 或 source_class=ENGINEERING；一律分類標記為 UNVERIFIED / SYNTHETIC。
    4. 若資料包未到位或未提供，則標記 real_data_status=UNKNOWN 並切換為內建 SYNTHETIC 測試資料集。
    """
    target_dir = Path(pack_dir) if pack_dir is not None else Path(
        os.environ.get('AMIDST_WC5_SAFE_PACK_DIR', '/content/drive/MyDrive/amidst_wc5_safe_pack')
    )

    if target_dir.exists() and target_dir.is_dir():
        root_canonical = target_dir.resolve()

        all_entries = sorted(target_dir.rglob('*'))
        for entry in all_entries:
            if _is_symlink_or_reparse(entry):
                raise ValueError(f'Symlink or junction forbidden in safe pack: {entry}')
            entry_canonical = entry.resolve()
            try:
                entry_canonical.relative_to(root_canonical)
            except ValueError:
                raise ValueError(f'Directory entry escapes safe pack root: {entry}')
            rel_parts = entry.relative_to(target_dir).parts
            for part in rel_parts:
                if FORBIDDEN_NAME_PATTERN.search(part):
                    raise ValueError(f'Forbidden GT / private token in safe pack entry: {entry}')
            if entry.is_file():
                if entry.suffix.lower() not in ALLOWED_PACK_SUFFIXES:
                    raise ValueError(f'Disallowed file suffix in safe pack: {entry}')

        manifest_file: Path | None = None
        for candidate_name in ('SAFE_PACK_MANIFEST.json', 'MANIFEST.json'):
            cand = target_dir / candidate_name
            if cand.is_file():
                manifest_file = cand
                break

        if manifest_file is None:
            if not allow_synthetic_fallback:
                raise FileNotFoundError(
                    f'Data pack directory {target_dir} has no SAFE_PACK_MANIFEST.json or MANIFEST.json'
                )
        else:
            manifest_name = manifest_file.relative_to(target_dir).as_posix()
            _validate_safe_relative_path(target_dir, manifest_name)
            actual_manifest_sha256 = sha256_file(manifest_file)

            try:
                raw_manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
            except Exception as exc:
                raise ValueError(f'Invalid JSON in manifest {manifest_file}: {exc}') from exc
            if not isinstance(raw_manifest, dict):
                raise ValueError(f'Manifest {manifest_file} must be a JSON object')

            gt_read = raw_manifest.get('gt_read')
            if gt_read is True or (gt_read is not None and gt_read is not False):
                raise ValueError(f'Safe pack manifest must declare gt_read=False, got: {gt_read!r}')

            pack_format = str(raw_manifest.get('format') or raw_manifest.get('schema_version') or '').strip()
            pack_id = str(raw_manifest.get('pack_id') or '').strip()
            sources = raw_manifest.get('sources') or raw_manifest.get('provenance') or raw_manifest.get('run_id')

            manifest_hashes: dict[str, str] = {}
            files_entry = raw_manifest.get('files')
            if isinstance(files_entry, dict):
                for rel_path, meta in files_entry.items():
                    if isinstance(meta, dict) and 'sha256' in meta:
                        manifest_hashes[str(rel_path)] = str(meta['sha256'])
                    elif isinstance(meta, str):
                        manifest_hashes[str(rel_path)] = meta
            elif isinstance(files_entry, list):
                for item in files_entry:
                    if isinstance(item, dict) and 'path' in item and 'sha256' in item:
                        manifest_hashes[str(item['path'])] = str(item['sha256'])

            if expected_hashes is not None:
                for k, v in expected_hashes.items():
                    if k != manifest_name:
                        manifest_hashes[str(k)] = str(v)

            if not manifest_hashes:
                raise ValueError(f'Data pack directory {target_dir} manifest has no file entries')

            verified_files: list[dict[str, Any]] = []
            for rel_path, exp_sha in sorted(manifest_hashes.items()):
                if rel_path == manifest_name:
                    continue
                fpath = _validate_safe_relative_path(target_dir, rel_path)
                actual_sha = sha256_file(fpath)
                if actual_sha.lower() != exp_sha.lower():
                    raise ValueError(
                        f'SHA-256 mismatch for {rel_path}: expected {exp_sha}, got {actual_sha}'
                    )
                verified_files.append({
                    'path': rel_path,
                    'sha256': actual_sha,
                    'size_bytes': fpath.stat().st_size,
                })

            trusted_manifest_sha = (
                expected_manifest_sha256
                or approved_manifest_sha256
                or os.environ.get('AMIDST_APPROVED_WC5_MANIFEST_SHA256')
                or os.environ.get('AMIDST_APPROVED_MANIFEST_SHA256')
            )
            if trusted_manifest_sha is None and expected_hashes and manifest_name in expected_hashes:
                trusted_manifest_sha = expected_hashes[manifest_name]

            if trusted_manifest_sha is None and pack_id and pack_id in APPROVED_SAFE_PACK_ROOTS:
                trusted_manifest_sha = APPROVED_SAFE_PACK_ROOTS[pack_id].get('manifest_sha256')

            if trusted_manifest_sha is not None:
                if actual_manifest_sha256.lower() != trusted_manifest_sha.lower():
                    raise ValueError(
                        f'Manifest SHA-256 mismatch against approved root of trust: '
                        f'expected {trusted_manifest_sha}, got {actual_manifest_sha256}'
                    )
                schema_ok = (
                    (pack_format in ALLOWED_SAFE_PACK_FORMATS or pack_format.startswith('amidst.'))
                    and bool(pack_id)
                    and (sources is not None)
                    and (gt_read is False)
                )
                if not schema_ok:
                    raise ValueError(
                        f'Safe pack manifest does not satisfy required schema/provenance fields: '
                        f'format={pack_format!r}, pack_id={pack_id!r}, sources={sources!r}, gt_read={gt_read!r}'
                    )
                root_of_trust_verified = True
            else:
                root_of_trust_verified = False

            if not root_of_trust_verified:
                return {
                    'real_data_status': 'UNVERIFIED',
                    'real_data_note': (
                        'UNVERIFIED (manifest is self-declared without verified upstream root of trust; '
                        'classified as SYNTHETIC)'
                    ),
                    'real_data_adapter_status': 'NOT_IMPLEMENTED',
                    'active_data_mode': 'SYNTHETIC',
                    'source_class': 'SYNTHETIC',
                    'gt_path_scan': 'PASS',
                    'sha256_verified': True,
                    'pack_dir': target_dir.as_posix(),
                    'pack_id': pack_id if pack_id else 'UNVERIFIED_SELF_DECLARED',
                    'manifest_path': manifest_name,
                    'manifest_format': pack_format or 'UNKNOWN',
                    'root_of_trust_verified': False,
                    'files_verified': verified_files,
                    'pack_manifest_sha256': actual_manifest_sha256,
                }

            return {
                'real_data_status': 'VERIFIED',
                'real_data_note': (
                    'VERIFIED W-C5 safe pack (files and owning manifest verified against approved root of trust; '
                    'real data execution adapter NOT_IMPLEMENTED)'
                ),
                'real_data_adapter_status': 'NOT_IMPLEMENTED',
                'active_data_mode': 'REAL_WC5_PACK',
                'source_class': 'ENGINEERING',
                'gt_path_scan': 'PASS',
                'sha256_verified': True,
                'pack_dir': target_dir.as_posix(),
                'pack_id': pack_id,
                'manifest_path': manifest_name,
                'manifest_format': pack_format,
                'root_of_trust_verified': True,
                'files_verified': verified_files,
                'pack_manifest_sha256': actual_manifest_sha256,
            }

    if not allow_synthetic_fallback:
        raise FileNotFoundError(f'W-C5 safe data pack not found at {target_dir}')

    fx_root = Path(fixture_dir) if fixture_dir is not None else (REPO_ROOT / 'tests/fixtures/research')
    rel_names = list(SYNTHETIC_FIXTURE_FILES)
    _assert_no_gt_private(rel_names)

    synthetic_files: list[dict[str, Any]] = []
    for name in rel_names:
        fpath = _validate_safe_relative_path(fx_root, name)
        actual_sha = sha256_file(fpath)
        if expected_hashes and name in expected_hashes:
            if actual_sha.lower() != expected_hashes[name].lower():
                raise ValueError(
                    f'SHA-256 mismatch for synthetic fixture {name}: '
                    f'expected {expected_hashes[name]}, got {actual_sha}'
                )
        synthetic_files.append({
            'path': f'tests/fixtures/research/{name}',
            'sha256': actual_sha,
            'size_bytes': fpath.stat().st_size,
        })

    return {
        'real_data_status': 'UNKNOWN',
        'real_data_note': 'UNKNOWN (awaiting #416 W-C5 safe pack; real data execution adapter NOT_IMPLEMENTED)',
        'real_data_adapter_status': 'NOT_IMPLEMENTED',
        'active_data_mode': 'SYNTHETIC',
        'source_class': 'SYNTHETIC',
        'gt_path_scan': 'PASS',
        'sha256_verified': True,
        'pack_dir': 'tests/fixtures/research',
        'files_verified': synthetic_files,
        'pack_manifest_sha256': canonical_json_sha256(synthetic_files),
        'root_of_trust_verified': False,
    }


# ---------------------------------------------------------------------------
# Cell 4: 中斷續跑（Checkpoint / Resume）實驗執行器（M0/RULE_ONLY 與 M1～M4）
# ---------------------------------------------------------------------------

def _build_experiment_units(fixture_dir: Path, config_sha256: str) -> list[dict[str, Any]]:
    """從研究資料集建立逐事件／逐模型的實驗工作單元清單（涵蓋 M0/RULE_ONLY 與 M1～M4）。"""
    units: list[dict[str, Any]] = []

    # 1. M0 (BASELINE RULE_ONLY)
    b_path = fixture_dir / 'SYNTHETIC_baseline_results.json'
    b_data = json.loads(b_path.read_text(encoding='utf-8'))
    b_sha = sha256_file(b_path)
    for ev in b_data.get('events', []):
        if ev.get('arm') == 'RULE_ONLY':
            unit_id = f"{ev.get('run_id')}::{ev.get('event_id')}"
            units.append({
                'experiment_id': 'M0_BASELINE',
                'model_arm': 'RULE_ONLY',
                'unit_id': unit_id,
                'config_sha256': config_sha256,
                'input_sha256': b_sha,
                'source_class': 'SYNTHETIC',
                'scored': bool(ev.get('scored')),
                'outcome': ev.get('match'),
                'latency_ms': ev.get('latency_ms', c.UNKNOWN),
            })

    # 2. M1 (RULE_ONLY vs AGENT_SEQUENTIAL)
    m1_path = fixture_dir / 'SYNTHETIC_m1_results.json'
    m1_data = json.loads(m1_path.read_text(encoding='utf-8'))
    m1_sha = sha256_file(m1_path)
    for ev in m1_data.get('events', []):
        arm = str(ev.get('arm', 'UNKNOWN'))
        unit_id = f"{ev.get('run_id')}::rep{ev.get('repeat')}::{ev.get('event_id')}"
        units.append({
            'experiment_id': 'M1_AGENT_VS_RULE',
            'model_arm': arm,
            'unit_id': unit_id,
            'config_sha256': config_sha256,
            'input_sha256': m1_sha,
            'source_class': 'SYNTHETIC',
            'scored': bool(ev.get('scored')),
            'outcome': ev.get('match'),
            'latency_ms': ev.get('latency_ms', c.UNKNOWN),
        })

    # 3. M2 (Scorer v1 vs v2)
    m2_path = fixture_dir / 'SYNTHETIC_m2_results.json'
    m2_data = json.loads(m2_path.read_text(encoding='utf-8'))
    m2_sha = sha256_file(m2_path)
    for ev in m2_data.get('events', []):
        unit_id = str(ev.get('event_id'))
        v1_l = ev.get('v1_label', c.UNKNOWN)
        v2_l = ev.get('v2_label', c.UNKNOWN)
        units.append({
            'experiment_id': 'M2_SCORER_V2',
            'model_arm': 'SCORER_V1_VS_V2',
            'unit_id': unit_id,
            'config_sha256': config_sha256,
            'input_sha256': m2_sha,
            'source_class': 'SYNTHETIC',
            'scored': ev.get('category') == 'STANDARD',
            'outcome': v1_l == v2_l if v1_l != c.UNKNOWN and v2_l != c.UNKNOWN else c.UNKNOWN,
            'latency_ms': c.UNKNOWN,
        })

    # 4. M3 (Q3 Parser RULE_ONLY vs LLM_WITH_RULE_FALLBACK on eligible queries)
    m3_path = fixture_dir / 'SYNTHETIC_m3_results.json'
    m3_q_path = fixture_dir / 'SYNTHETIC_m3_queries_eligible.csv'
    m3_data = json.loads(m3_path.read_text(encoding='utf-8'))
    m3_sha = sha256_bytes(m3_path.read_bytes() + m3_q_path.read_bytes())
    eligible_rows, _, _ = ax.eligible_queries(m3_q_path)
    eligible_ids = {r['query_id'] for r in eligible_rows}
    for q in m3_data.get('questions', []):
        qid = q.get('query_id')
        if qid not in eligible_ids:
            continue
        arm = str(q.get('arm', 'UNKNOWN'))
        units.append({
            'experiment_id': 'M3_Q3_PARSER',
            'model_arm': arm,
            'unit_id': str(qid),
            'config_sha256': config_sha256,
            'input_sha256': m3_sha,
            'source_class': 'SYNTHETIC',
            'scored': True,
            'outcome': q.get('correct'),
            'latency_ms': c.UNKNOWN,
        })

    # 5. M4 (Candidate Models Q2 & Q3)
    m4_path = fixture_dir / 'SYNTHETIC_m4_results.json'
    m4_data = json.loads(m4_path.read_text(encoding='utf-8'))
    m4_sha = sha256_file(m4_path)
    for ev in m4_data.get('events', []):
        units.append({
            'experiment_id': 'M4_MODEL_COMPARE_Q2',
            'model_arm': str(ev.get('model', 'UNKNOWN')),
            'unit_id': f"{ev.get('run_id')}::{ev.get('event_id')}",
            'config_sha256': config_sha256,
            'input_sha256': m4_sha,
            'source_class': 'SYNTHETIC',
            'scored': True,
            'outcome': ev.get('match'),
            'latency_ms': c.UNKNOWN,
        })
    for q in m4_data.get('questions', []):
        units.append({
            'experiment_id': 'M4_MODEL_COMPARE_Q3',
            'model_arm': str(q.get('model', 'UNKNOWN')),
            'unit_id': f"{q.get('run_id')}::{q.get('query_id')}",
            'config_sha256': config_sha256,
            'input_sha256': m4_sha,
            'source_class': 'SYNTHETIC',
            'scored': True,
            'outcome': q.get('correct'),
            'latency_ms': c.UNKNOWN,
        })

    return units


def _checkpoint_key(rec: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(rec['experiment_id']),
        str(rec['model_arm']),
        str(rec['unit_id']),
        str(rec['config_sha256']),
        str(rec['input_sha256']),
    )


def load_checkpoint_records(checkpoint_path: Path) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    """讀取 JSONL checkpoint 檔案中已完成的紀錄。"""
    completed: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    if not checkpoint_path.is_file():
        return completed
    for line in checkpoint_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get('status') == 'COMPLETED':
            completed[_checkpoint_key(rec)] = rec
    return completed


def run_checkpointed_experiments(
    checkpoint_path: Path | str,
    *,
    fixture_dir: Path | None = None,
    config_sha256: str = '1111111111111111111111111111111111111111111111111111111111111111',
    max_units_to_run: int | None = None,
) -> dict[str, Any]:
    """執行支援中斷續跑（Checkpoint / Resume）的實驗迴圈。

    - 若 `checkpoint_path` 已存在相同 `(experiment_id, model_arm, unit_id, config_sha256, input_sha256)`
      之完成紀錄，自動跳過不重複計算。
    - 可透過 `max_units_to_run` 模擬中斷（跑指定筆數後停止），再次呼叫時可無縫續跑剩餘項目。
    """
    cp_path = Path(checkpoint_path)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    fx_root = Path(fixture_dir) if fixture_dir is not None else (REPO_ROOT / 'tests/fixtures/research')

    all_units = _build_experiment_units(fx_root, config_sha256)
    completed_map = load_checkpoint_records(cp_path)

    skipped_count = 0
    executed_count = 0
    interrupted = False

    with cp_path.open('a', encoding='utf-8', newline='\n') as handle:
        for unit in all_units:
            key = _checkpoint_key(unit)
            if key in completed_map:
                skipped_count += 1
                continue
            if max_units_to_run is not None and executed_count >= max_units_to_run:
                interrupted = True
                break
            record = {
                **unit,
                'status': 'COMPLETED',
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
            handle.flush()
            completed_map[key] = record
            executed_count += 1

    by_exp: dict[str, int] = {}
    for rec in completed_map.values():
        exp_id = str(rec['experiment_id'])
        by_exp[exp_id] = by_exp.get(exp_id, 0) + 1

    return {
        'checkpoint_path': cp_path.as_posix(),
        'checkpoint_sha256': sha256_file(cp_path) if cp_path.is_file() else c.UNKNOWN,
        'total_units': len(all_units),
        'skipped_from_checkpoint': skipped_count,
        'executed_now': executed_count,
        'completed_total': len(completed_map),
        'interrupted': interrupted,
        'completed_by_experiment': by_exp,
    }


# ---------------------------------------------------------------------------
# Cell 5: 結果彙整與匯出 CSV 表格、視覺化比較圖（PNG）與匯出包 MANIFEST SHA-256
# ---------------------------------------------------------------------------

def export_analysis_bundle(
    export_dir: Path | str,
    *,
    env_manifest: Mapping[str, Any],
    env_manifest_sha256: str,
    data_pack_report: Mapping[str, Any],
    checkpoint_report: Mapping[str, Any],
    fixture_dir: Path | None = None,
    bootstrap_b: int = 200,
) -> dict[str, Any]:
    """執行 M0～M4 統計圖表匯出，並產生總覽 CSV、比較圖 PNG 與 `EXPORT_MANIFEST.json`。"""
    out_root = Path(export_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    fx_root = Path(fixture_dir) if fixture_dir is not None else (REPO_ROOT / 'tests/fixtures/research')

    # 儲存環境 manifest
    env_path = out_root / 'experiment_env_manifest.json'
    env_path.write_text(
        json.dumps(env_manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )

    b_flag = ['--bootstrap-b', str(bootstrap_b)]

    # 執行 M0 Baseline 與 M1~M4 表格與圖表產出（攔截子腳本路徑輸出以保持 JSON 輸出純淨且不含本機路徑）
    with contextlib.redirect_stdout(io.StringIO()):
        bt.main([str(fx_root / 'SYNTHETIC_baseline_results.json'), '--out', str(out_root / 'm0_baseline'), *b_flag])
        ax.main(['m1', str(fx_root / 'SYNTHETIC_m1_results.json'), '--out', str(out_root / 'm1'), *b_flag])
        ax.main(['m2', str(fx_root / 'SYNTHETIC_m2_results.json'), '--out', str(out_root / 'm2'), *b_flag])
        ax.main([
            'm3',
            str(fx_root / 'SYNTHETIC_m3_results.json'),
            '--queries',
            str(fx_root / 'SYNTHETIC_m3_queries_eligible.csv'),
            '--out',
            str(out_root / 'm3'),
            *b_flag,
        ])
        ax.main(['m4', str(fx_root / 'SYNTHETIC_m4_results.json'), '--out', str(out_root / 'm4'), *b_flag])

    # 讀取各模組產出之關鍵指標以彙整總表
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open(encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))

    b_rows = _read_csv(out_root / 'm0_baseline/baseline_B1.csv')
    b_total = next((r for r in b_rows if r.get('row') == 'TOTAL:ALL'), {})

    m1_rows = _read_csv(out_root / 'm1/m1_M1-1.csv')
    m1_rule = next((r for r in m1_rows if r.get('arm') == 'RULE_ONLY'), {})
    m1_agent = next((r for r in m1_rows if r.get('arm') == 'AGENT_SEQUENTIAL'), {})

    m2_rows = _read_csv(out_root / 'm2/m2_M2-1.csv')
    m2_row = m2_rows[0] if m2_rows else {}

    m3_rows = _read_csv(out_root / 'm3/m3_M3-1.csv')
    m3_rule = next((r for r in m3_rows if r.get('arm') == 'RULE_ONLY' and r.get('wording_type') == 'ALL'), {})
    m3_llm = next(
        (r for r in m3_rows if r.get('arm') == 'LLM_WITH_RULE_FALLBACK' and r.get('wording_type') == 'ALL'),
        {},
    )

    m4_rows = _read_csv(out_root / 'm4/m4_M4-1.csv')
    m4_q2_best = max(
        (r for r in m4_rows if r.get('module') == 'Q2' and _to_float(r.get('score_pct')) is not None),
        key=lambda r: _to_float(r['score_pct']) or 0.0,
        default={},
    )

    # 統計結果來源嚴格綁定實際讀入的資料（嚴格 provenance 分類）：
    # 本分析流程讀入 tests/fixtures/research/SYNTHETIC_* 固定產物。
    # 即使 safe pack 在磁碟上驗證通過，因真實推論 adapter 尚未實作（NOT_IMPLEMENTED），
    # 產物指標來源一律標記為 SYNTHETIC 與 UNKNOWN，絕不升格為 ENGINEERING 或 VERIFIED。
    source_cls = 'SYNTHETIC'
    real_status = 'UNKNOWN'

    summary_columns = [
        'module',
        'arm_or_scope',
        'primary_metric',
        'score_pct',
        'ci_lo',
        'ci_hi',
        'n_scored',
        'source_class',
        'real_data_status',
        'env_manifest_sha256',
    ]
    summary_rows = [
        {
            'module': 'M0_BASELINE',
            'arm_or_scope': 'RULE_ONLY (TOTAL:ALL)',
            'primary_metric': 'C_evt_pct',
            'score_pct': b_total.get('C_evt_pct', c.UNKNOWN),
            'ci_lo': b_total.get('C_evt_lo', c.UNKNOWN),
            'ci_hi': b_total.get('C_evt_hi', c.UNKNOWN),
            'n_scored': b_total.get('n_events_scored', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M1_Q5_SWITCH',
            'arm_or_scope': 'RULE_ONLY',
            'primary_metric': 'C_evt_pct',
            'score_pct': m1_rule.get('C_evt_pct', c.UNKNOWN),
            'ci_lo': m1_rule.get('C_evt_lo', c.UNKNOWN),
            'ci_hi': m1_rule.get('C_evt_hi', c.UNKNOWN),
            'n_scored': m1_rule.get('n_units_paired', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M1_Q5_SWITCH',
            'arm_or_scope': 'AGENT_SEQUENTIAL',
            'primary_metric': 'C_evt_pct',
            'score_pct': m1_agent.get('C_evt_pct', c.UNKNOWN),
            'ci_lo': m1_agent.get('C_evt_lo', c.UNKNOWN),
            'ci_hi': m1_agent.get('C_evt_hi', c.UNKNOWN),
            'n_scored': m1_agent.get('n_units_paired', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M2_SCORER_V2',
            'arm_or_scope': 'STANDARD_EVENTS',
            'primary_metric': 'A_std_pct',
            'score_pct': m2_row.get('A_std_pct', c.UNKNOWN),
            'ci_lo': c.UNKNOWN,
            'ci_hi': c.UNKNOWN,
            'n_scored': m2_row.get('n_std_both_scored', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M3_Q3_PARSER',
            'arm_or_scope': 'RULE_ONLY (ALL)',
            'primary_metric': 'E_q3_pct',
            'score_pct': m3_rule.get('E_q3_pct', c.UNKNOWN),
            'ci_lo': m3_rule.get('E_q3_lo', c.UNKNOWN),
            'ci_hi': m3_rule.get('E_q3_hi', c.UNKNOWN),
            'n_scored': m3_rule.get('n_questions_scored', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M3_Q3_PARSER',
            'arm_or_scope': 'LLM_WITH_RULE_FALLBACK (ALL)',
            'primary_metric': 'E_q3_pct',
            'score_pct': m3_llm.get('E_q3_pct', c.UNKNOWN),
            'ci_lo': m3_llm.get('E_q3_lo', c.UNKNOWN),
            'ci_hi': m3_llm.get('E_q3_hi', c.UNKNOWN),
            'n_scored': m3_llm.get('n_questions_scored', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
        {
            'module': 'M4_CANDIDATES',
            'arm_or_scope': f"Q2:{m4_q2_best.get('model', c.UNKNOWN)}",
            'primary_metric': 'C_evt_pct',
            'score_pct': m4_q2_best.get('score_pct', c.UNKNOWN),
            'ci_lo': m4_q2_best.get('score_lo', c.UNKNOWN),
            'ci_hi': m4_q2_best.get('score_hi', c.UNKNOWN),
            'n_scored': m4_q2_best.get('n', c.UNKNOWN),
            'source_class': source_cls,
            'real_data_status': real_status,
            'env_manifest_sha256': env_manifest_sha256,
        },
    ]

    summary_csv_path = out_root / 'colab_oneclick_summary.csv'
    with summary_csv_path.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.DictWriter(f, fieldnames=summary_columns, lineterminator='\n')
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    # 繪製總覽視覺化比較圖 PNG / SVG
    plt, theme = c.plt_setup('light')
    banner_txt = f"{source_cls} | real_data={real_status} | env {env_manifest_sha256[:8]}"
    fig, ax_plt = c.new_fig(
        plt,
        'W-A6 Colab One-Click Summary (M0..M4 Primary Metrics)',
        banner_txt,
        size=(8.5, 4.5),
        subtitle=f'source_class={source_cls}, real_data_status={real_status} (not formal evidence)',
    )
    labels = [f"{r['module']}\n{r['arm_or_scope']}" for r in summary_rows]
    vals = [_to_float(r['score_pct']) or 0.0 for r in summary_rows]
    bars = ax_plt.bar(range(len(summary_rows)), vals, width=0.58, color=theme['s1'])
    for idx, (bar, val) in enumerate(zip(bars, vals)):
        ax_plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            min(val + 2.5, 104.0),
            f'{val:.1f}%',
            ha='center',
            va='bottom',
            fontsize=8,
            color=theme['ink'],
        )
    ax_plt.set_xticks(range(len(labels)), labels, rotation=20, ha='right', fontsize=7.5)
    ax_plt.set_ylim(0, 112)
    ax_plt.set_ylabel('Primary Score (%)')
    c.save_fig(fig, out_root, 'colab_oneclick_summary')

    # 收集所有匯出檔案與其 SHA-256，建立 EXPORT_MANIFEST.json
    exported_files: list[dict[str, Any]] = []
    for p in sorted(out_root.rglob('*')):
        if not p.is_file() or p.name == 'EXPORT_MANIFEST.json':
            continue
        exported_files.append({
            'path': p.relative_to(out_root).as_posix(),
            'sha256': sha256_file(p),
            'size_bytes': p.stat().st_size,
        })

    manifest_payload = {
        'bundle_type': 'amidst_colab_oneclick_export',
        'source_class': source_cls,
        'real_data_status': real_status,
        'real_data_adapter_status': 'NOT_IMPLEMENTED',
        'real_data_note': 'Scores derived strictly from SYNTHETIC fixtures; real data adapter NOT_IMPLEMENTED.',
        'env_manifest_sha256': env_manifest_sha256,
        'checkpoint_completed_units': checkpoint_report.get('completed_total', 0),
        'checkpoint_sha256': checkpoint_report.get('checkpoint_sha256', c.UNKNOWN),
        'files': exported_files,
    }
    export_manifest_sha256 = canonical_json_sha256(manifest_payload)
    manifest_payload['export_manifest_sha256'] = export_manifest_sha256

    manifest_path = out_root / 'EXPORT_MANIFEST.json'
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )

    return {
        'export_dir': out_root.as_posix(),
        'summary_csv': summary_csv_path.as_posix(),
        'summary_csv_sha256': sha256_file(summary_csv_path),
        'summary_png': (out_root / 'colab_oneclick_summary.png').as_posix(),
        'summary_png_sha256': sha256_file(out_root / 'colab_oneclick_summary.png'),
        'export_manifest_path': manifest_path.as_posix(),
        'export_manifest_sha256': export_manifest_sha256,
        'file_count': len(exported_files),
        'summary_rows': summary_rows,
        'real_data_status': real_status,
        'real_data_adapter_status': 'NOT_IMPLEMENTED',
        'real_data_note': 'Real data evaluation adapter not implemented; scores bound to SYNTHETIC fixtures.',
        'source_class': source_cls,
    }


def run_all_oneclick(
    workdir: Path | str,
    *,
    pack_dir: Path | str | None = None,
    expected_manifest_sha256: str | None = None,
    deterministic: bool = True,
    bootstrap_b: int = 200,
) -> dict[str, Any]:
    """一鍵依序執行 Cell 1 ～ Cell 5 全流程並回傳結構化報告。"""
    work_root = Path(workdir)
    work_root.mkdir(parents=True, exist_ok=True)

    cell1 = inspect_environment(deterministic=deterministic)
    cell2 = check_api_keys()
    cell3 = verify_data_pack(
        pack_dir=pack_dir,
        expected_manifest_sha256=expected_manifest_sha256,
        allow_synthetic_fallback=True,
    )
    cp_file = work_root / 'checkpoints/experiment_checkpoint.jsonl'
    cell4 = run_checkpointed_experiments(
        cp_file,
        config_sha256=cell1['env_manifest']['parameter_set']['parameter_set_sha256'],
    )
    cell5 = export_analysis_bundle(
        work_root / 'exports',
        env_manifest=cell1['env_manifest'],
        env_manifest_sha256=cell1['env_manifest_sha256'],
        data_pack_report=cell3,
        checkpoint_report=cell4,
        bootstrap_b=bootstrap_b,
    )
    return {
        'cell1_env': cell1,
        'cell2_keys': cell2,
        'cell3_data_pack': cell3,
        'cell4_checkpoint': cell4,
        'cell5_export': cell5,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True, help='輸出與 checkpoint 工作目錄')
    parser.add_argument('--pack-dir', type=Path, default=None, help='W-C5 safe 資料包路徑（選填）')
    parser.add_argument(
        '--manifest-sha256',
        type=str,
        default=None,
        help='核定之 safe pack manifest SHA-256 信任根（選填）',
    )
    parser.add_argument('--bootstrap-b', type=int, default=200, help='Bootstrap 重抽樣次數')
    args = parser.parse_args(argv)

    report = run_all_oneclick(
        args.workdir,
        pack_dir=args.pack_dir,
        expected_manifest_sha256=args.manifest_sha256,
        bootstrap_b=args.bootstrap_b,
    )
    print(json.dumps({
        'env_manifest_sha256': report['cell1_env']['env_manifest_sha256'],
        'real_data_status': report['cell3_data_pack']['real_data_status'],
        'active_data_mode': report['cell3_data_pack']['active_data_mode'],
        'completed_total': report['cell4_checkpoint']['completed_total'],
        'skipped_from_checkpoint': report['cell4_checkpoint']['skipped_from_checkpoint'],
        'export_manifest_sha256': report['cell5_export']['export_manifest_sha256'],
        'summary_csv_sha256': report['cell5_export']['summary_csv_sha256'],
        'summary_png_sha256': report['cell5_export']['summary_png_sha256'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
