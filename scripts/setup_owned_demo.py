"""Provision the checkout from uv.lock and the Node lock; never use a legacy venv."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from demo_dependency_config import REPO, MIN_FREE, configuration, owned_path


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--offline', action='store_true'); args = parser.parse_args()
    config, root = configuration()
    if shutil.disk_usage(root).free < MIN_FREE:
        raise SystemExit('DISK_BELOW_8_GIB')
    node_version = subprocess.check_output(['node', '--version'], text=True).strip().removeprefix('v')
    if node_version != config['node']['tested_version']:
        raise SystemExit('NODE_VERSION: use the repository .node-version')
    # This captured local runtime profile is darwin-arm64. Other OS provisioning is
    # a separate C acceptance target; data/model hashes are platform independent.
    python = owned_path(root, config['python_base'])/'bin/python3.12'
    if not python.is_file():
        raise SystemExit('OWNED_PYTHON_PROFILE_MISSING: transfer the matching owned runtime profile')
    env = dict(os.environ, UV_CACHE_DIR=str(REPO/'.local/demo-cache/uv'), UV_NO_MANAGED_PYTHON='1')
    uv = ['uv']
    if not (REPO/'.venv').exists():
        subprocess.run([*uv, 'venv', '--offline', '--no-project', '--no-python-downloads', '--python', str(python), '.venv'], cwd=REPO, env=env, check=True)
    local_python = REPO/'.venv/bin/python'
    subprocess.run([*uv, 'sync', *(['--offline'] if args.offline else []), '--frozen', '--no-install-project', '--link-mode', 'copy', '--no-python-downloads', '--python', str(local_python)], cwd=REPO, env=env, check=True)
    subprocess.run(['npm', 'ci', '--prefix', config['node']['package_root'], *(['--offline'] if args.offline else []), '--ignore-scripts', '--no-audit', '--no-fund'], cwd=REPO, check=True)
    env['PYTHONPATH'] = str(REPO/'src'); env['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.run([*uv, 'run', '--offline', '--no-project', '--python', str(local_python), 'python', '-B', 'scripts/check_demo_dependencies.py', '--smoke'], cwd=REPO, env=env, check=True)


if __name__ == '__main__':
    main()
