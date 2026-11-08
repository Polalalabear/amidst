"""Owned demo paths and runtime boundary. Manifests are versioned in the repository."""
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
MIN_FREE = 8 * 1024**3


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
        raise ValueError('CANONICAL_OWNED_ROOT_REQUIRED: set AMIDST_DEMO_HOME to the transferred owned package')
    manifest = owned_path(REPO, config['dependency_manifest']).read_bytes()
    if hashlib.sha256(manifest).hexdigest() != config['dependency_manifest_sha256']:
        raise ValueError('REPOSITORY_DEPENDENCY_MANIFEST_PIN_MISMATCH')
    return config, root


def resolve_job(job, root):
    # Original frozen input bytes/pins are unchanged; only the new job's locators resolve.
    for reference in [job['graph'], *(ref for run in job['runs'] for ref in run['inputs'].values())]:
        reference['path'] = str(owned_path(root, reference['path']))
    return job


def install_owned_io_guard(root):
    """Fail if runtime opens home/TMP inputs outside this checkout and owned package.

    Old asset paths may remain opaque provenance inside immutable copied JSON. They
    cannot become filesystem inputs. OS resources remain available; no model process
    or outbound connection is part of the recorded-data demo.
    """
    if Path(sys.prefix).resolve() != (REPO/'.venv').resolve():
        raise ValueError('CHECKOUT_VENV_REQUIRED')
    if not Path(sys.base_prefix).resolve().is_relative_to(root/'runtime'):
        raise ValueError('OWNED_PYTHON_BASE_REQUIRED')
    seen = set()
    home = Path.home().resolve()

    def audit(event, args):
        if event in {'subprocess.Popen', 'socket.connect'}:
            raise ValueError('RECORDED_DEMO_NO_EXTERNAL_PROCESS_OR_CONNECTION')
        if event not in {'open', 'os.listdir', 'os.scandir'} or not args or isinstance(args[0], int):
            return
        value = args[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(value)).resolve()
        if path.is_relative_to(root):
            seen.add('owned/'+str(path.relative_to(root)))
            return
        if path.is_relative_to(REPO):
            seen.add('repo/'+str(path.relative_to(REPO)))
            return
        if path.is_relative_to(home) or path.is_relative_to('/Users/Shared') or path.is_relative_to('/private/tmp'):
            raise ValueError('EXTERNAL_LOCAL_INPUT_DENIED')
    sys.addaudithook(audit)
    return seen
