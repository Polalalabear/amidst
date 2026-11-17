#!/usr/bin/env python3
"""Write an `amidst.provenance-record.v1` JSON record (git SHA, input SHA-256, model digest, hardware).

Safety: never reads environment variables into the record (fixed whitelist of fields only), refuses
Ground Truth / visibility / depth / trajectory paths and `gt_private/`, never opens a network
connection other than an optional loopback query to a local Ollama. Provenance only; no approval.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

SCHEMA = 'amidst.provenance-record.v1'
UNKNOWN = 'UNKNOWN'
CHUNK = 1 << 20
PACKAGES = ('numpy', 'pydantic', 'pillow', 'shapely', 'networkx', 'matplotlib', 'pytest',
            'psycopg', 'rerun-sdk')
# Any path component (case-insensitive) that equals/contains one of these is refused.
FORBIDDEN_PARTS = ('gt_private', 'ground_truth', 'ground-truth', 'groundtruth')
FORBIDDEN_TOKENS = {'gt', 'visibility', 'depth', 'trajectory', 'trajectories'}
SECRET_ARG = re.compile(
    r'(?i)(\b[\w.-]*(?:key|secret|token|passw(?:or)?d|credential)[\w.-]*\s*[=:]\s*)\S+'
    r'|(--[\w-]*(?:key|secret|token|passw(?:or)?d)[\w-]*[ =])\S+|\b(?:sk|ghp|gho|xox[a-z])[-_][\w-]{8,}')


class ProvenanceError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def is_forbidden(path):
    """True when any component of the path names GT, visibility, depth or trajectory data."""
    for part in Path(path).parts:
        low = part.lower()
        if any(item in low for item in FORBIDDEN_PARTS):
            return True
        if FORBIDDEN_TOKENS & set(re.split(r'[^a-z0-9]+', low.rsplit('.', 1)[0] if '.' in low else low)):
            return True
    return False


def checked_path(raw):
    path = Path(raw)
    for candidate in (path, path.resolve()):  # also catches a symlink that leads into GT data
        if is_forbidden(candidate):
            raise ProvenanceError('FORBIDDEN_PATH: refusing GT/visibility/depth/trajectory path')
    if not path.exists():
        raise ProvenanceError(f'MISSING_PATH: {raw}')
    return path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_input(raw):
    """File → one entry. Directory → one entry per file plus a digest over the sorted listing."""
    path = checked_path(raw)
    if path.is_file():
        return {'path': str(raw), 'kind': 'file', 'bytes': path.stat().st_size, 'sha256': sha256_file(path)}
    files = []
    for item in sorted(p for p in path.rglob('*') if p.is_file()):
        checked_path(item)
        files.append({'path': item.relative_to(path).as_posix(), 'bytes': item.stat().st_size,
                      'sha256': sha256_file(item)})
    tree = hashlib.sha256(''.join(f"{f['path']}\0{f['sha256']}\n" for f in files).encode()).hexdigest()
    return {'path': str(raw), 'kind': 'directory', 'file_count': len(files),
            'bytes': sum(f['bytes'] for f in files), 'tree_sha256': tree, 'files': files}


def ollama_digest(name, tags=None):
    """Full digest from a local Ollama /api/tags; UNKNOWN when it cannot be read."""
    try:
        if tags is None:
            with urlopen('http://127.0.0.1:11434/api/tags', timeout=3) as resp:  # loopback only
                tags = json.loads(resp.read())
        for model in tags.get('models', []):
            if name in (model.get('name'), model.get('model')) or f'{name}:latest' == model.get('name'):
                digest = model.get('digest')
                return digest if isinstance(digest, str) and digest else UNKNOWN
    except Exception:  # noqa: BLE001 — any failure means "not readable"
        pass
    return UNKNOWN


def run(*cmd, timeout=10):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def git_info(repo):
    repo = str(repo)
    head = run('git', '-C', repo, 'rev-parse', 'HEAD')
    status = run('git', '-C', repo, 'status', '--porcelain')
    if head is None or status is None:
        return {'head_sha': UNKNOWN, 'branch': UNKNOWN, 'dirty': UNKNOWN, 'dirty_entries': UNKNOWN}
    entries = [line for line in status.splitlines() if line]
    return {'head_sha': head, 'branch': run('git', '-C', repo, 'branch', '--show-current') or 'DETACHED',
            'dirty': bool(entries), 'dirty_entries': len(entries),
            'working_tree': 'DIRTY — results are not reproducible from head_sha alone' if entries else 'clean'}


def memory_bytes():
    if sys.platform == 'darwin':
        value = run('sysctl', '-n', 'hw.memsize')
        return int(value) if value and value.isdigit() else UNKNOWN
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return UNKNOWN


def cpu_name():
    if sys.platform == 'darwin':
        return run('sysctl', '-n', 'machdep.cpu.brand_string') or platform.processor() or UNKNOWN
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or UNKNOWN


def gpu_info(probe=True):
    if not probe:
        return UNKNOWN
    if shutil.which('nvidia-smi'):
        out = run('nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader')
        if out:
            return [line.strip() for line in out.splitlines()]
    if sys.platform == 'darwin':
        out = run('system_profiler', '-json', 'SPDisplaysDataType', timeout=20)
        try:
            return [d.get('sppci_model', UNKNOWN) for d in json.loads(out)['SPDisplaysDataType']] or UNKNOWN
        except Exception:  # noqa: BLE001
            pass
    return UNKNOWN


def package_versions():
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = UNKNOWN
    return versions


def environment(probe_gpu=True):
    return {
        'os': {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine()},
        'cpu': {'name': cpu_name(), 'logical_cores': os.cpu_count() or UNKNOWN},
        'memory_bytes': memory_bytes(),
        'gpu': gpu_info(probe_gpu),
        'python': {'version': platform.python_version(), 'implementation': platform.python_implementation()},
        'packages': package_versions(),
        'node': (run('node', '--version') or UNKNOWN),
    }


def redact(text):
    return SECRET_ARG.sub(lambda m: (m.group(1) or m.group(2) or '') + '[REDACTED]', text)


def build_record(args, started=None):
    repo = Path(args.repo).resolve()
    models = [{'kind': 'weights_file', **{k: v for k, v in hash_input(p).items() if k != 'files'}}
              for p in args.model_file]
    models += [{'kind': 'ollama', 'name': name, 'digest': ollama_digest(name)} for name in args.ollama_model]
    return {
        'schema_version': SCHEMA,
        'generated_at_utc': utc_now(),
        'run': {'command': redact(args.command or ' '.join(sys.argv)), 'label': args.label or None,
                'started_at_utc': args.started_at or started, 'finished_at_utc': args.finished_at or utc_now()},
        'git': git_info(repo),
        'inputs': [hash_input(p) for p in args.input],
        'models': models,
        'environment': environment(not args.skip_gpu_probe),
        'script': {'path': 'scripts/provenance_record.py', 'sha256': sha256_file(__file__)},
        'notes': 'Provenance only: grants no approval. GT, visibility, depth and trajectory paths are refused; '
                 'environment variables are never recorded.',
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--input', action='append', default=[], metavar='PATH', help='file, manifest or directory to hash')
    p.add_argument('--model-file', action='append', default=[], metavar='PATH', help='weights file to digest')
    p.add_argument('--ollama-model', action='append', default=[], metavar='NAME')
    p.add_argument('--command', help='the command being recorded (secrets are redacted)')
    p.add_argument('--label')
    p.add_argument('--started-at', help='UTC ISO-8601 start time of the recorded run')
    p.add_argument('--finished-at', help='UTC ISO-8601 end time of the recorded run')
    p.add_argument('--skip-gpu-probe', action='store_true', help='record GPU as UNKNOWN (faster)')
    p.add_argument('--output', type=Path, help='write JSON here (default: stdout)')
    args = p.parse_args(argv)
    try:
        record = build_record(args)
    except ProvenanceError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.write_text(raw, encoding='utf-8')
    else:
        print(raw, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
