"""Copy an explicit #486 dependency plan into a new owned root; never remove sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time

MIN_FREE = 8 * 1024**3
BLOCK = 1024**2
FORBIDDEN_PARTS = {'gt_private', 'ground_truth', '.env'}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()


def destination(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts and bool(p.parts), 'RELATIVE_DESTINATION_REQUIRED')
    target = root / p
    require(target.resolve().is_relative_to(root), 'DESTINATION_ESCAPE')
    require(not FORBIDDEN_PARTS.intersection(p.parts), 'PROTECTED_PATH')
    return target


def collect(plan_path):
    plan = json.loads(plan_path.read_bytes())
    root = Path(plan['destination'])
    require(root.is_absolute() and root.resolve() == root and not root.exists(), 'NEW_CANONICAL_ROOT_REQUIRED')
    require(root.parent.is_dir(), 'PARENT_REQUIRED')
    entries = plan['entries']; free = shutil.disk_usage(root.parent).free
    total = sum(e['bytes'] for e in entries if e['kind'] == 'file')
    require(free >= MIN_FREE + total + plan['reserve_bytes'], 'PROJECTED_DISK_BELOW_8_GIB')
    require(len({e['destination'] for e in entries}) == len(entries), 'DUPLICATE_DESTINATION')
    for e in entries:
        src = Path(e['source']); dst = destination(root, e['destination'])
        require(not FORBIDDEN_PARTS.intersection(src.parts), 'PROTECTED_SOURCE')
        require(src.is_absolute() and src.lstat().st_size == e['bytes'], 'SOURCE_DRIFT')
        require(e['kind'] in {'file', 'symlink'}, 'SOURCE_KIND')
        if e['kind'] == 'symlink':
            require(src.is_symlink() and os.readlink(src) == e['target'] and not Path(e['target']).is_absolute(), 'UNSAFE_LINK')
            require((dst.parent/e['target']).resolve().is_relative_to(root), 'EXTERNAL_LINK')
        else:
            require(not src.is_symlink() and stat.S_ISREG(src.stat().st_mode), 'REGULAR_SOURCE_REQUIRED')
    root.mkdir(); minimum_free = free; results = []; started = time.monotonic()
    # Copy exact files only. No cleanup, move, original rewrite, model or renderer call.
    for n, e in enumerate(entries):
        available = shutil.disk_usage(root).free; minimum_free = min(minimum_free, available)
        require(available >= MIN_FREE + (e['bytes'] if e['kind'] == 'file' else 0), 'DISK_BELOW_8_GIB')
        src = Path(e['source']); dst = destination(root, e['destination']); dst.parent.mkdir(parents=True, exist_ok=True)
        require(not dst.exists() and not dst.is_symlink(), 'DESTINATION_EXISTS')
        if e['kind'] == 'symlink':
            dst.symlink_to(e['target']); row = {**e, 'verified': 'INTERNAL_RELATIVE_LINK'}
        else:
            h = hashlib.sha256(); size = 0
            with src.open('rb') as source, dst.open('xb') as target:
                while block := source.read(BLOCK):
                    require(shutil.disk_usage(root).free >= MIN_FREE + len(block), 'DISK_BELOW_8_GIB')
                    target.write(block); h.update(block); size += len(block)
            require(size == e['bytes'] and (e.get('sha256') is None or h.hexdigest() == e['sha256']), 'SOURCE_HASH_OR_SIZE_MISMATCH')
            require(digest(dst) == h.hexdigest(), 'COPY_HASH_MISMATCH')
            shutil.copystat(src, dst, follow_symlinks=False)
            row = {**e, 'sha256': h.hexdigest(), 'verified': 'BYTE_IDENTICAL'}
        results.append(row)
        if n % 500 == 0:
            print(json.dumps({'copied': n+1, 'files': len(entries), 'free_bytes': available}), flush=True)
    job_path = root/'metadata/cross-camera-job.json'; job_path.parent.mkdir(exist_ok=True)
    job_path.write_text(json.dumps(plan['relative_job'], indent=2)+'\n')
    manifest = {'version': 1, 'source_head': plan['source_head'], 'copy_plan_sha256': digest(plan_path),
        'file_count': len(results), 'total_file_bytes': total, 'elapsed_s': time.monotonic()-started,
        'minimum_free_bytes': minimum_free, 'source_mutations': False, 'files': results,
        'relative_job': {'path': str(job_path.relative_to(root)), 'sha256': digest(job_path)}}
    (root/'copy-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'destination': str(root), 'files': len(results),
                      'bytes': total, 'manifest_sha256': digest(root/'copy-manifest.json'),
                      'job_sha256': digest(job_path), 'free_bytes': shutil.disk_usage(root).free}), flush=True)


def verify_sources(receipt_path):
    manifest = json.loads(receipt_path.read_bytes()); count = links = total = 0
    for entry in manifest['files']:
        src = Path(entry['source'])
        require(not FORBIDDEN_PARTS.intersection(src.resolve().parts), 'PROTECTED_SOURCE')
        require(src.lstat().st_size == entry['bytes'], 'SOURCE_SIZE_DRIFT')
        if entry['kind'] == 'symlink':
            require(src.is_symlink() and os.readlink(src) == entry['target'], 'SOURCE_LINK_DRIFT')
            links += 1
        else:
            require(not src.is_symlink() and digest(src) == entry['sha256'], 'SOURCE_HASH_DRIFT')
            count += 1; total += entry['bytes']
    print(json.dumps({'status': 'PASS', 'source_entries': count+links,
                      'regular_files': count, 'relative_links': links, 'file_bytes': total,
                      'receipt_sha256': digest(receipt_path), 'original_writes': False}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', type=Path); mode.add_argument('--verify-sources', type=Path)
    args = p.parse_args()
    if args.plan:
        collect(args.plan)
    else:
        verify_sources(args.verify_sources)
