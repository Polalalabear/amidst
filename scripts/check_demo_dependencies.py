"""Verify the committed owned manifest, locked environment and all four real RGB sources."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
from urllib.parse import parse_qs, urlsplit

from demo_dependency_config import REPO, MIN_FREE, configuration, owned_path, install_owned_io_guard


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def verify(config_path=None, *, smoke=False):
    config, root = configuration(config_path)
    require(shutil.disk_usage(root).free >= MIN_FREE, 'DISK_BELOW_8_GIB')
    manifest = json.loads((REPO/config['dependency_manifest']).read_bytes())
    require(manifest['schema_version'] == 'amidst.demo-owned-files.v1', 'MANIFEST_SCHEMA')
    paths = set(); total = 0; entries_by_path = {e['path']: e for e in manifest['files']}
    for entry in manifest['files']:
        rel = Path(entry['path'])
        require(not rel.is_absolute() and '..' not in rel.parts and str(rel) not in paths, 'MANIFEST_PATH')
        require(not {'gt_private', 'ground_truth', '.env'}.intersection(rel.parts), 'PROTECTED_PATH')
        paths.add(str(rel)); path = root/rel
        require(path.resolve().is_relative_to(root), 'COPY_ESCAPE')
        require(path.lstat().st_size == entry['bytes'], 'OWNED_SIZE_MISMATCH:'+str(rel))
        if entry['kind'] == 'symlink':
            require(path.is_symlink() and os.readlink(path) == entry['target'], 'OWNED_LINK_MISMATCH')
        else:
            require(not path.is_symlink() and path.is_file() and sha(path) == entry['sha256'], 'OWNED_HASH_MISMATCH:'+str(rel))
        total += entry['bytes']
    node_lock_bytes = (REPO/config['node']['package_root']/'package-lock.json').read_bytes()
    node_lock = json.loads(node_lock_bytes)
    node_package = REPO/config['node']['package_root']/'node_modules/playwright-core'
    require(json.loads((node_package/'package.json').read_bytes())['version'] == node_lock['packages']['node_modules/playwright-core']['version'], 'NODE_LOCK_VERSION')
    node_files = 0
    for entry in manifest['files']:
        if entry['group'] == 'PLAYWRIGHT':
            relative = Path(entry['path']).relative_to('tooling/playwright-core')
            require(sha(node_package/relative) == entry['sha256'], 'NODE_PACKAGE_BYTES_MISMATCH')
            node_files += 1
    ollama = owned_path(root, config['models']['ollama_models'])
    model = json.loads((ollama/'manifests/registry.ollama.ai/library/qwen3/1.7b-q4_K_M').read_bytes())
    model_digests = []
    for item in [model['config'], *model['layers']]:
        require(item['digest'].startswith('sha256:'), 'MODEL_DIGEST_KIND')
        digest = item['digest'].removeprefix('sha256:')
        entry = entries_by_path['models/ollama/blobs/sha256-'+digest]
        require(entry['sha256'] == digest and entry['bytes'] == item['size'], 'OLLAMA_BLOB_BINDING')
        model_digests.append(digest)
    lock_bytes = (REPO/'uv.lock').read_bytes(); lock = tomllib.loads(lock_bytes.decode())
    canon = lambda s: s.lower().replace('_', '-')
    locked = {(canon(p['name']), p['version']) for p in lock['package']}
    installed = sorted({(canon(d.metadata['Name']), d.version) for d in importlib.metadata.distributions()})
    require(all(p in locked for p in installed), 'INSTALLED_DISTRIBUTION_NOT_IN_UV_LOCK')
    require(any(p[0] == 'pytest' for p in installed), 'DEV_DEPENDENCIES_REQUIRED')
    require(sys.version.split()[0] == config['python_version'], 'PYTHON_VERSION')
    seen = install_owned_io_guard(root)
    try:
        (Path.home()/'__amidst_external_input_probe__').open('rb')
    except ValueError as exc:
        require(str(exc) == 'EXTERNAL_LOCAL_INPUT_DENIED', 'NEGATIVE_IO_PROBE')
    else:
        raise ValueError('EXTERNAL_IO_GUARD_INACTIVE')
    modules = []
    for module in tuple(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file and str(file).startswith(str(Path.home())):
            require(Path(file).resolve().is_relative_to(REPO) or Path(file).resolve().is_relative_to(root), 'FOREIGN_IMPORTED_MODULE')
            modules.append(str(Path(file).resolve()))
    sources = []
    if smoke:
        from serve_demo_integration import Demo
        state_root = owned_path(root, config['state_root']); state_root.mkdir(exist_ok=True)
        state = Path(tempfile.mkdtemp(prefix='dependency-check-', dir=state_root))/'state'
        app = Demo(owned_path(root, config['artifacts_root']), owned_path(root, config['p1_bundle']), state,
                   job_path=owned_path(root, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'], owned_root=root)
        boot = app.bootstrap(); require(boot.get('demo_integration') is True and len(boot['runs']) == 4, 'FOUR_SOURCE_BOOTSTRAP')
        token = app.call('session', {'role': 'demo'})['session_ref']
        for run in boot['runs']:
            payload = {'session_ref': token, 'scene_id': run['scene_id'], 'run_id': run['run_id'], 't_s': 0, 'camera_ids': run['camera_ids'][:1]}
            frame = app.rgb.call('synced_frames', payload); tile = frame['tiles'][0]
            require(tile['status'] == 'READY', 'REAL_RGB_UNAVAILABLE')
            grant = parse_qs(urlsplit(tile['media_url']).query)['token'][0]
            raw = app.rgb.media(grant)
            require(raw.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(raw).hexdigest() == tile['served_sha256'], 'SERVED_RGB_HASH')
            sources.append({'run_id': run['run_id'], 'source_kind': run['source_kind'], 'served_sha256': tile['served_sha256']})
    require(shutil.disk_usage(root).free >= MIN_FREE, 'DISK_BELOW_8_GIB')
    return {'status': 'PASS', 'source_head': manifest['source_head'], 'manifest_sha256': config['dependency_manifest_sha256'],
            'entries': len(paths), 'bytes': total, 'node_package_files': node_files,
            'node_lock_sha256': hashlib.sha256(node_lock_bytes).hexdigest(), 'ollama_blob_digests': model_digests,
            'negative_io_probe_denied': True, 'uv_lock_sha256': hashlib.sha256(lock_bytes).hexdigest(),
            'python': sys.version.split()[0], 'python_prefix': str(Path(sys.prefix)), 'base_prefix': str(Path(sys.base_prefix)),
            'distributions': [{'name': n, 'version': v} for n, v in installed], 'imported_owned_modules': len(modules),
            'guarded_file_opens': len(seen), 'sources': sources, 'free_bytes': shutil.disk_usage(root).free,
            'models_executed': False, 'renders': False, 'source_mutations': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path); parser.add_argument('--output', type=Path); parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args(); result = verify(args.config, smoke=args.smoke)
    data = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(data)
    print(data, end='')


if __name__ == '__main__':
    main()
