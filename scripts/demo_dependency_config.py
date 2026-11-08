"""Owned #486 configuration. Only explicit relative dependency references resolve."""
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def owned_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or '..' in path.parts:
        raise ValueError('OWNED_RELATIVE_PATH_REQUIRED')
    result = root / path
    if result.resolve() != result or not result.resolve().is_relative_to(root):
        raise ValueError('OWNED_PATH_ESCAPE_OR_SYMLINK')
    return result


def configuration(path=None):
    path = Path(path or REPO/'configs/demo_integration_local.json')
    config = json.loads(path.read_bytes())
    if config['version'] != 1:
        raise ValueError('OWNED_CONFIG_VERSION')
    root = Path(os.environ.get('AMIDST_DEMO_HOME', config['owned_root'])).expanduser()
    if not root.is_absolute() or root.resolve() != root or not root.is_dir():
        raise ValueError('CANONICAL_OWNED_ROOT_REQUIRED')
    manifest = owned_path(root, 'copy-manifest.json').read_bytes()
    if hashlib.sha256(manifest).hexdigest() != config['copy_manifest_sha256']:
        raise ValueError('OWNED_COPY_MANIFEST_PIN_MISMATCH')
    return config, root


def resolve_job(job, root):
    # Preserve immutable original input bytes and pins; only job locators change.
    for reference in [job['graph'], *(ref for run in job['runs'] for ref in run['inputs'].values())]:
        reference['path'] = str(owned_path(root, reference['path']))
    return job
