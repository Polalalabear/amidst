"""D124 safe-bundle RGB adapter for explicit, non-formal DEMO_DEFAULT indexing.

Metadata is pinned before any RGB byte is read. No GT, scene script, or private
path is accepted. This adapter does not grant production parameter approval.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import os
import stat

MIN_FREE_BYTES = 8 * 1024**3
EXPECTED_BUNDLE_SHA256 = 'ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01'


class DemoIndexError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise DemoIndexError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def loads(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(DemoIndexError('NONFINITE_JSON')))


def safe_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and '\\' not in relative, 'UNSAFE_PATH')
    rel = PurePosixPath(relative)
    require(not rel.is_absolute() and rel.as_posix() == relative and '..' not in rel.parts
            and (relative == 'MANIFEST.json' or rel.parts[0] in {'rgb', 'runs', 'clocks', 'provenance'}), 'UNSAFE_PATH')
    current = root
    require(not current.is_symlink(), 'SYMLINK_ROOT')
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink(), 'SYMLINK_PATH')
    require(current.is_file() and current.resolve().is_relative_to(root.resolve()), 'MISSING_OR_OUTSIDE_PATH')
    return current


def read_pinned(root: Path, relative: str, expected: str, *, metadata: bool = False) -> bytes:
    require(isinstance(expected, str) and len(expected) == 64 and all(c in '0123456789abcdef' for c in expected), 'INVALID_PIN')
    path = safe_path(root, relative)
    if metadata:
        require(path.suffix == '.json' and path.stat().st_size <= 4_000_000, 'METADATA_SIZE_OR_TYPE')
    before = path.lstat()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require(stat.S_ISREG(opened.st_mode) and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'FILE_CHANGED')
        raw = stream.read(16_777_217)
    require(len(raw) == opened.st_size and len(raw) <= 16_777_216 and not path.is_symlink(), 'FILE_CHANGED_OR_TOO_LARGE')
    require(sha(raw) == expected, 'BYTE_PIN_MISMATCH:' + relative)
    return raw


def free_space(path: Path) -> int:
    free = shutil.disk_usage(path).free
    require(free >= MIN_FREE_BYTES, f'LOW_DISK:{free}:{MIN_FREE_BYTES}')
    return free


class D124DemoRun:
    """Minimal SafeRun interface backed solely by pinned D124 safe-bundle RGB."""

    def __init__(self, root: Path, config: dict):
        self.root = Path(root).absolute()
        require(self.root.is_dir() and not self.root.is_symlink(), 'SAFE_ROOT_REQUIRED')
        require(config.get('profile') == 'DEMO_DEFAULT' and config.get('formal_eligible') is False,
                'DEMO_PROFILE_REQUIRED')
        require(config.get('safe_manifest_sha256') == EXPECTED_BUNDLE_SHA256,
                'D124_BUNDLE_PIN_REQUIRED')
        bundle = loads(read_pinned(self.root, 'MANIFEST.json', EXPECTED_BUNDLE_SHA256, metadata=True))
        inventory = bundle.get('files')
        require(isinstance(inventory, dict) and isinstance(bundle.get('runs'), list), 'BUNDLE_SHAPE')
        for relative, pin in inventory.items():
            require(isinstance(pin, str) and len(pin) == 64
                    and all(c in '0123456789abcdef' for c in pin), 'INVENTORY_PIN_INVALID')
            safe_path(self.root, relative)  # Names and links only; no payload bytes.
        require(set(bundle['runs']) == {'runs/A4-1.json', 'runs/B4-1.json'}, 'D124_RUN_SET_MISMATCH')
        run_rel = config.get('run_descriptor')
        require(run_rel in bundle['runs'] and inventory.get(run_rel) == config.get('run_descriptor_sha256'), 'RUN_PIN_MISMATCH')
        descriptor = loads(read_pinned(self.root, run_rel, inventory[run_rel], metadata=True))
        clock_rel = descriptor.get('clock_ref')
        require(inventory.get(clock_rel) == config.get('clock_sha256'), 'CLOCK_PIN_MISMATCH')
        clock = loads(read_pinned(self.root, clock_rel, inventory[clock_rel], metadata=True))
        catalog_rel = 'provenance/camera_catalog.json'
        require(inventory.get(catalog_rel) == config.get('catalog_sha256') == descriptor.get('catalog_sha256'), 'CATALOG_PIN_MISMATCH')
        catalog = loads(read_pinned(self.root, catalog_rel, inventory[catalog_rel], metadata=True))
        require(clock.get('run_id') == descriptor.get('run_id') == config.get('run_id')
                and clock.get('clock_id') == config.get('clock_id'), 'RUN_CLOCK_MISMATCH')
        require(config.get('scene_id') and config.get('scene_revision') == 'r004', 'SCENE_BINDING_REQUIRED')
        fps = descriptor.get('sampling', {}).get('fps')
        require(type(fps) is int and fps > 0 and 1_000_000 % fps == 0, 'SOURCE_FPS_INVALID')
        camera_ids = descriptor.get('camera_ids')
        require(isinstance(camera_ids, list) and camera_ids and len(set(camera_ids)) == len(camera_ids), 'CAMERA_SET_INVALID')
        camera_map = {c['camera_id']: c for c in catalog.get('cameras', [])}
        require(set(camera_ids) <= set(camera_map), 'CAMERA_CATALOG_MISMATCH')
        sizes = {(camera_map[c]['width'], camera_map[c]['height']) for c in camera_ids}
        require(len(sizes) == 1, 'IMAGE_SIZE_MISMATCH')
        frames = descriptor.get('frames')
        require(isinstance(frames, list) and frames, 'FRAMES_REQUIRED')
        rows = {}
        for frame in frames:
            c, i, rel, pin = (frame.get(k) for k in ('camera_id', 'frame_index', 'filename', 'file_sha256'))
            require(c in camera_ids and type(i) is int and i >= 0 and (c, i) not in rows,
                    'FRAME_GRID_OR_DUPLICATE')
            require(inventory.get(rel) == pin and isinstance(rel, str) and rel.startswith('rgb/'), 'FRAME_INVENTORY_PIN')
            require(rel == f"rgb/{descriptor['run_id']}/{c}/frame_{i:06d}.png", 'FRAME_PATH_SCOPE')
            safe_path(self.root, rel)  # Reject symlinks before any model load.
            rows[c, i] = {'file_sha256': pin, 'timestamp_s': i / fps, 'path': rel}
        counts = {c: len([1 for camera, _ in rows if camera == c]) for c in camera_ids}
        require(len(set(counts.values())) == 1, 'UNEQUAL_CAMERA_GRID')
        count = next(iter(counts.values()))
        require(count > 0 and set(rows) == {(c, i) for c in camera_ids for i in range(count)}, 'INCOMPLETE_CAMERA_GRID')
        require(clock.get('source_duration_us') == count * (1_000_000 // fps), 'CLOCK_DURATION_MISMATCH')
        self.camera_ids = tuple(camera_ids)
        self._rows = rows
        projection = [{'camera_id': c, 'frame_index': i, 'file_sha256': rows[c, i]['file_sha256']}
                      for c in sorted(camera_ids) for i in range(count)]
        rgb_index_pin = sha(canonical(projection))
        self.manifest = {
            'scene_id': config['scene_id'], 'run_id': descriptor['run_id'], 'clock_id': clock['clock_id'],
            'sampling': {'fps': fps, 'duration_s': count / fps, 'sample_count_per_camera': count,
                         'image_size_px': list(next(iter(sizes)))},
            'allowlist': [{'role': 'rgb_index', 'file_sha256': rgb_index_pin}],
        }
        self.files = {'rgb_index': {'records': projection, 'missing': []}}
        self.source_projection = {
            'profile': 'DEMO_DEFAULT', 'formal_eligible': False,
            'safe_manifest_sha256': EXPECTED_BUNDLE_SHA256,
            'run_descriptor': run_rel, 'run_descriptor_sha256': inventory[run_rel],
            'clock_ref': clock_rel, 'clock_sha256': inventory[clock_rel],
            'catalog_ref': catalog_rel, 'catalog_sha256': inventory[catalog_rel],
            'rgb_index_projection_sha256': rgb_index_pin,
            'run_id': descriptor['run_id'], 'clock_id': clock['clock_id'],
            'scene_id': config['scene_id'], 'scene_revision': config['scene_revision'],
            'camera_ids': list(camera_ids), 'fps': fps, 'sample_count_per_camera': count,
        }

    def rgb_record(self, camera_id: str, frame_index: int):
        row = self._rows.get((camera_id, frame_index))
        return {k: row[k] for k in ('file_sha256', 'timestamp_s')} if row else None

    def read_rgb(self, camera_id: str, frame_index: int):
        row = self._rows.get((camera_id, frame_index))
        require(row is not None, 'RGB_NOT_IN_SOURCE_GRID')
        free_space(self.root)
        return read_pinned(self.root, row['path'], row['file_sha256'])
