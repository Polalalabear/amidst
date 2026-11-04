"""Shared CLI and read/write guards for the #415 local authoring tools."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

MIN_FREE_BYTES = 8 * 1024**3


def argv_after_separator(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    return args[args.index('--') + 1:] if '--' in args else args


def parser(description):
    return argparse.ArgumentParser(description=description)


def require(value, code):
    if not value:
        raise ValueError(code)


def checked_path(value):
    """Reject private namespaces and links before opening any component."""
    path = Path(value).absolute()
    for index, part in enumerate(path.parts):
        if index == 1 and part == 'private' and len(path.parts) > 2 and path.parts[2] in {'tmp', 'var'}:
            continue  # macOS filesystem root, not a data namespace.
        tokens = re.split(r'[^a-z0-9]+', part.lower())
        require(not ({'gt', 'private', 'trajectory', 'trajectories', 'visibility', 'depth'} & set(tokens)),
                'PRIVATE_PATH_FORBIDDEN')
    for item in reversed((path, *path.parents)):
        require(not item.is_symlink(), 'SYMLINK_FORBIDDEN')
        require(not getattr(item, 'is_junction', lambda: False)(), 'JUNCTION_FORBIDDEN')
    require(path.resolve() == path, 'NONCANONICAL_PATH')
    return path


def read_bytes(path):
    path = checked_path(path)
    require(path.is_file(), 'INPUT_FILE_MISSING')
    return path.read_bytes()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    path = checked_path(path)
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def canonical_hash(doc):
    return digest(json.dumps(doc, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode())


def pinned(path, expected):
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'SHA256_REQUIRED')
    raw = read_bytes(path)
    require(digest(raw) == expected, 'INPUT_SHA256_MISMATCH')
    return raw


def disk(path, reserve_bytes=0):
    path = checked_path(path)
    while not path.exists():
        path = path.parent
    free = shutil.disk_usage(path).free
    require(free >= MIN_FREE_BYTES + reserve_bytes, 'DISK_BELOW_8_GIB_OR_RESERVE')
    return free


def new_output(path):
    path = checked_path(path)
    require(path.parent.is_dir(), 'OUTPUT_PARENT_MISSING')
    require(not path.exists(), 'OUTPUT_ALREADY_EXISTS')
    disk(path.parent)
    path.mkdir()
    return path


def write_bytes(path, raw):
    path = checked_path(path)
    disk(path.parent, len(raw))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def write_json(path, doc):
    write_bytes(path, (json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())


def authorize(args):
    require(args.execute and args.authorization_ref.strip(), 'EXECUTION_AUTHORIZATION_REQUIRED')


def execution_options(p):
    p.add_argument('--execute', action='store_true', help='Execute only after separate user authorization.')
    p.add_argument('--authorization-ref', default='', help='Reference to the explicit authorization.')
