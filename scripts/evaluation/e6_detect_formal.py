#!/usr/bin/env python3
"""E6 formal recording -> frozen RGB (PNG) + RT-DETR detection index, through the SAME pipeline and parameters as E3 (#732 G4, zero cost).

The only producer is ``scripts/evaluation/e3_cases/index.py`` (E3 #652: wire receipts + camera JPEGs -> rgb/<case> PNGs ->
RT-DETR R18 letterbox person index, upper-HSV colour, score floor 0.05). It is called unchanged. Nothing new is detected per arm later:
B1, R-N, AO_ORIG and the E6 arms all read this one output.

Isolation: the output root is a fresh folder that holds only APFS clones of ``<case>.replay1.wire.json`` and ``pixels/<case>/``
from the recording (the recording folder itself is never written). Case/GT/a-log/scenario files are never copied, so the
detector cannot see them. The frozen recording MANIFEST is verified for every cloned file first.

Parity gate: the detector block, colour method, sampling and record format of the first produced index must equal a reference E3 index
(``--reference-index``), apart from fields listed as allowed; any other difference stops the run (no receipt).
Writes ``DETECTION_RECEIPT.json`` (weights SHA-256, RT-DETR source commit, torch/torchvision versions, device, code SHA-256s, per-case
index/records/RGB-index SHA-256) in the output root. Stops when free disk < --min-free-gib (default 5).

  python e6_detect_formal.py --recording local/evidence/e6-formal-20261127 --out local/evidence/e6-formal-det-20261127 \
      --models local/data/demo-owned-v1/models/rtdetr --runtime-deps local/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps \
      --reference-index local/evidence/e3-652-20261122/indexes/E3-A1/detection_index.json [--cases E6-S01]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_PY = ROOT / 'scripts/evaluation/e3_cases/index.py'
SCHEMA = 'e6.detection-receipt.v1'
CODE_FILES = ('scripts/evaluation/e3_cases/index.py', 'src/amidst/q1q5/detection_index.py', 'src/amidst/live_mode/detector.py',
              'src/amidst/q1q5/hsv_color.py', 'scripts/evaluation/e6_detect_formal.py')
PARITY_ALLOWED_DIFF = {'detector.device'}          # CPU vs MPS would be recorded, not hidden; everything else must be equal
FORBIDDEN_NAME_PARTS = ('case.json', 'a-log', 'gt-boxes', 'e6-scenario', 'scenarios_frozen')
SPEC_NAME = 'e6_scenarios_frozen_v1.json'


class DetectionError(RuntimeError):
    pass


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(recording: Path) -> dict[str, str]:
    out = {}
    for line in (recording / 'MANIFEST.sha256').read_text().splitlines():
        if line.strip():
            digest, rel = line.split('  ', 1)
            out[rel] = digest
    return out


def required_files(recording: Path, case_id: str) -> list[str]:
    """Wire receipt plus every pixel it lists; the wire is the only index of what the inference side may see."""
    wire = f'{case_id}.replay1.wire.json'
    doc = json.loads((recording / wire).read_text())
    files = [wire]
    for capture in doc:
        files += [f['path'] for f in capture['frames']]
    return files


def verify_against_manifest(recording: Path, manifest: dict[str, str], files: list[str]) -> None:
    for rel in files:
        want = manifest.get(rel)
        if want is None:
            raise DetectionError(f'NOT_IN_MANIFEST: {rel}')
        if sha_file(recording / rel) != want:
            raise DetectionError(f'MANIFEST_SHA_MISMATCH: {rel}')


def clone(src: Path, dst: Path, recursive=False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['cp', '-c', *(['-R'] if recursive else []), str(src), str(dst)], capture_output=True)
    if r.returncode:
        raise DetectionError(f'CLONE_FAILED {src}: {r.stderr.decode()[:120]}')


def prepare_root(recording: Path, out: Path, case_id: str) -> None:
    """Clone only the wire receipt and the pixels directory of one case (never case/GT/a-log files)."""
    wire = out / f'{case_id}.replay1.wire.json'
    if not wire.exists():
        clone(recording / f'{case_id}.replay1.wire.json', wire)
    if not (out / 'pixels' / case_id).exists():
        clone(recording / 'pixels' / case_id, out / 'pixels' / case_id, recursive=True)


def isolation_violations(out: Path) -> list[str]:
    """Names in the output root that must never exist there (GT / case / scenario files)."""
    bad = []
    for p in out.rglob('*'):
        rel = p.relative_to(out).as_posix()
        if p.is_file() and not rel.startswith('pixels/') and not rel.startswith('rgb/') and any(s in rel for s in FORBIDDEN_NAME_PARTS):
            bad.append(rel)
        if p.is_dir() and p.name in ('gt', 'gt-boxes', 'ground_truth'):
            bad.append(rel + '/')
    return bad


def flatten(d, prefix=''):
    out = {}
    for k, v in d.items():
        key = f'{prefix}.{k}' if prefix else k
        out.update(flatten(v, key) if isinstance(v, dict) else {key: v})
    return out


def parity_differences(new: dict, ref: dict) -> list[str]:
    """Differences between two detection_index.json documents in the fields that define the pipeline (not per-case ids/hashes)."""
    diffs = []
    if sorted(new) != sorted(ref):
        diffs.append(f'top_level_keys:{sorted(set(new) ^ set(ref))}')
    for part in ('detector', 'color_method', 'schema_version', 'scene_revision'):
        a, b = flatten({part: new.get(part)}), flatten({part: ref.get(part)})
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k) and k not in PARITY_ALLOWED_DIFF:
                diffs.append(f'{k}: {a.get(k)!r} != {b.get(k)!r}')
    sa, sb = new.get('sampling') or {}, ref.get('sampling') or {}
    for k in ('fps', 'image_size_px'):
        if sa.get(k) != sb.get(k):
            diffs.append(f'sampling.{k}: {sa.get(k)!r} != {sb.get(k)!r}')
    return diffs


def records_key_parity(new_records: Path, ref_records: Path) -> list[str]:
    a = json.loads(new_records.open().readline())
    b = json.loads(ref_records.open().readline())
    out = []
    if sorted(a) != sorted(b):
        out.append(f'record_keys:{sorted(set(a) ^ set(b))}')
    da, db = (a.get('detections') or [{}])[0], (b.get('detections') or [{}])[0]
    if da and db and sorted(da) != sorted(db):
        out.append(f'detection_keys:{sorted(set(da) ^ set(db))}')
    return out


def build_receipt(out: Path, cases: list[str], *, recording: Path, spec_sha: str, manifest_sha: str, weights_sha: str,
                  device: str, commit: str, parity: dict, created=None) -> dict:
    per_case = {}
    detector = None
    for cid in cases:
        idx = json.loads((out / 'indexes' / cid / 'detection_index.json').read_text())
        prod = json.loads((out / 'indexes' / cid / 'production.json').read_text())
        detector = detector or idx['detector']
        if idx['detector'] != detector:
            raise DetectionError(f'DETECTOR_BLOCK_VARIES_ACROSS_CASES:{cid}')
        records = out / 'indexes' / cid / idx['records_ref']
        persons = sum(1 for line in records.read_text().splitlines() for d in json.loads(line)['detections'] if d.get('class_label') == 'person')
        per_case[cid] = {'frames': prod['frames'], 'elapsed_s': round(prod['elapsed_s'], 1), 'gt_read': prod['gt_read'],
                         'index_content_sha256': idx['content_sha256'], 'index_file_sha256': prod['index_file_sha256'],
                         'records_file_sha256': prod['records_file_sha256'], 'rgb_index_sha256': idx['rgb_index_sha256'],
                         'person_detections_retained': persons}
    return {'schema_version': SCHEMA, 'created_utc': (created or dt.datetime.now(dt.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'identity': 'UNCONFIRMED', 'paid_calls': 0, 'gt_read': any(v['gt_read'] for v in per_case.values()),
            'recording_manifest_sha256': manifest_sha, 'frozen_spec_sha256': spec_sha,
            'detector': detector, 'weights_file_sha256_verified': weights_sha, 'device': device, 'code_commit_sha': commit,
            'code_sha256': {r: (sha_file(ROOT / r) if (ROOT / r).is_file() else 'UNKNOWN_FILE_ABSENT') for r in CODE_FILES},
            'parity_with_e3': parity, 'cases': per_case,
            'note': 'single producer = e3_cases/index.py; every group reads these PNGs and this index (no per-arm redetection)'}


def git_head() -> str:
    return subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()


def default_runner(out: Path, models: Path, cases: list[str], device: str, runtime_deps: Path | None) -> None:
    env = dict(os.environ)
    paths = [str(ROOT / 'src')] + ([str(runtime_deps)] if runtime_deps else [])
    env['PYTHONPATH'] = os.pathsep.join(paths + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    subprocess.run([sys.executable, '-B', str(INDEX_PY), '--root', str(out), '--models', str(models), '--cases', *cases,
                    '--device', device], env=env, check=True)


def run(a, runner=default_runner) -> dict:
    recording, out = Path(a.recording), Path(a.out)
    free = shutil.disk_usage(out.parent if out.parent.exists() else Path('/')).free / 2**30
    if free < a.min_free_gib:
        raise DetectionError(f'DISK_LOW: {free:.1f} GiB < {a.min_free_gib}')
    spec_path = Path(a.spec) if a.spec else recording / SPEC_NAME
    spec = json.loads(spec_path.read_text())
    cases = list(a.cases) if a.cases else [c['case_id'] for c in spec['formal_cases']]
    unknown = sorted(set(cases) - {c['case_id'] for c in spec['formal_cases']})
    if unknown:
        raise DetectionError(f'NOT_FORMAL_CASES: {unknown}')
    manifest = read_manifest(recording)
    for cid in cases:
        verify_against_manifest(recording, manifest, required_files(recording, cid))
    out.mkdir(parents=True, exist_ok=True)
    for cid in cases:
        prepare_root(recording, out, cid)
    todo = [c for c in cases if not (out / 'indexes' / c).exists()]
    for c in cases:
        if c not in todo:
            print('SKIP_EXISTS', c, flush=True)
    weights = Path(a.models) / 'rtdetr_r18vd_dec3_6x_coco_from_paddle.pth'
    weights_sha = sha_file(weights)
    if todo:
        runner(out, Path(a.models), todo, a.device, Path(a.runtime_deps) if a.runtime_deps else None)
    parity = {'reference_index': 'UNKNOWN (not given)', 'differences': None}
    if a.reference_index:
        ref = Path(a.reference_index)
        first = json.loads((out / 'indexes' / cases[0] / 'detection_index.json').read_text())
        diffs = parity_differences(first, json.loads(ref.read_text()))
        ref_records = ref.parent / json.loads(ref.read_text())['records_ref']
        diffs += records_key_parity(out / 'indexes' / cases[0] / first['records_ref'], ref_records)
        if json.loads(ref.read_text())['detector']['weights_file_sha256'] != weights_sha:
            diffs.append('weights_file_sha256 != reference')
        parity = {'reference_index': str(ref), 'reference_index_file_sha256': sha_file(ref), 'differences': diffs}
        if diffs:
            raise DetectionError('PARITY_WITH_E3_FAILED: ' + '; '.join(diffs))
    bad = isolation_violations(out)
    if bad:
        raise DetectionError('ISOLATION_VIOLATION: ' + ', '.join(bad[:5]))
    receipt = build_receipt(out, cases, recording=recording, spec_sha=sha_file(spec_path), manifest_sha=sha_file(recording / 'MANIFEST.sha256'),
                            weights_sha=weights_sha, device=a.device, commit=git_head(), parity=parity)
    (out / 'DETECTION_RECEIPT.json').write_text(json.dumps(receipt, indent=1, ensure_ascii=False, allow_nan=False) + '\n')
    return receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--recording', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--models', type=Path, required=True, help='folder with rtdetr_r18vd_dec3_6x_coco_from_paddle.pth and source/rtdetr_pytorch')
    ap.add_argument('--runtime-deps', type=Path, help='folder with torch 2.6.0 / torchvision 0.21.0 (PYTHONPATH of the child)')
    ap.add_argument('--spec', type=Path, help=f'frozen spec (default <recording>/{SPEC_NAME})')
    ap.add_argument('--reference-index', type=Path, help='an E3 detection_index.json for the parity gate')
    ap.add_argument('--cases', nargs='+')
    ap.add_argument('--device', default='mps', choices=['cpu', 'mps'])
    ap.add_argument('--min-free-gib', type=float, default=5.0)
    a = ap.parse_args(argv)
    try:
        r = run(a)
    except DetectionError as exc:
        print('DETECTION_FAILED', exc, file=sys.stderr)
        return 5
    print('DETECTION_OK', json.dumps({'cases': sorted(r['cases']), 'parity_differences': r['parity_with_e3']['differences']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
