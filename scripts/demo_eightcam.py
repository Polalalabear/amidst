"""Load the existing #529 A4-1 and B4-1 safe observations for the workbench."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.store import DocumentPin, JsonRunStore
from demo_dependency_config import REPO, owned_path
from run_cross_camera_demo import loads, read_pin, require

RUN_ID = 'r004-4actor-natural-walk-eightcam-20261114-a4-1'
TITLE = 'A4-1-8CAM · 4 人／8 鏡頭 · ACTUAL_BLENDER'
BUNDLE_DIR = 'r004-4actor-natural-walk-eightcam-20261114'
BUNDLE_PREFIX = f'data/{BUNDLE_DIR}/bundle/safe/'
RECEIPT = REPO / 'docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json'
RUN_DESCRIPTOR = 'runs/A4-1.json'
CLOCK = 'clocks/A4-1.json'
CONFIG = 'config/A4-1.json'
CATALOG = 'provenance/camera_catalog.json'
GRAPH = 'provenance/camera_graph_v3_1.json'
INDEX = 'indexes/A4-1/detection_index.json'
RECORDS = 'indexes/A4-1/detection_index.records.jsonl'
METADATA = (RUN_DESCRIPTOR, CLOCK, CONFIG, CATALOG, GRAPH, INDEX, RECORDS)
RUN_SPECS = {
    'A4-1': {'run_id': RUN_ID, 'title': TITLE, 'duration_us': 50_000_000, 'samples': 250},
    'B4-1': {'run_id': 'r004-4actor-natural-walk-eightcam-20261114-b4-1',
             'title': 'B4-1-8CAM · 4 人／8 鏡頭 · ACTUAL_BLENDER',
             'duration_us': 42_000_000, 'samples': 210},
}


def metadata_for(label):
    return (f'runs/{label}.json', f'clocks/{label}.json', f'config/{label}.json',
            CATALOG, GRAPH, f'indexes/{label}/detection_index.json',
            f'indexes/{label}/detection_index.records.jsonl')



class _EightCamIndexStore(JsonRunStore):
    def _read(self, pin):
        # The external audit allowlist grants exact file reads. Use the shared
        # bounded pin reader instead of the owned store's directory-relative opens.
        path = owned_path(self.root, pin.path)
        return read_pin({'path': str(path), 'sha256': pin.file_sha256})


@dataclass(frozen=True)
class EightCamSource:
    root: Path
    pins: dict[str, str]
    label: str = 'A4-1'

    @property
    def run_id(self):
        return RUN_SPECS[self.label]['run_id']

    @property
    def title(self):
        return RUN_SPECS[self.label]['title']

    @property
    def sources(self):
        return tuple(EightCamSource(self.root, self.pins, label) for label in RUN_SPECS)

    @property
    def read_files(self):
        return tuple(self.root / relative for relative in self.pins)

    def document(self, name):
        return loads(read_pin({'path': str(owned_path(self.root, name)), 'sha256': self.pins[name]}))

    def load(self):
        run_path, clock_path, config_path, _, _, index_path, records_path = metadata_for(self.label)
        spec = RUN_SPECS[self.label]
        samples = spec['samples']
        run = self.document(run_path)
        clock = ClockMapping(self.document(clock_path))
        settings = self.document(config_path)
        catalog = self.document(CATALOG)
        graph = self.document(GRAPH)
        source = self.document(index_path)

        index = _EightCamIndexStore(self.root, {
            'index': DocumentPin(index_path, self.pins[index_path], 'q-demo.detection-index.v1',
                                 source['content_sha256']),
            'records': DocumentPin(records_path, self.pins[records_path], 'q-demo.detection-record.v1'),
        }).load_detection_index('index')
        require(source['provenance']['gt_read'] is False and settings['formal_eligible'] is False,
                'EIGHTCAM_ENGINEERING_SCOPE')
        require(source['scene_id'] == run['scene_id'] == settings['scene_id']
                and source['scene_revision'] == run['scene_revision'] == settings['scene_revision'],
                'EIGHTCAM_SCENE_BINDING')
        require(source['run_id'] == run['run_id'] == settings['run_id'] == self.run_id
                and source['clock_id'] == run['clock_id'] == settings['clock_id'] == clock.clock_id
                and clock.duration_us == run['duration_us'] == spec['duration_us']
                and settings['clock_sha256'] == self.pins[clock_path]
                and settings['run_descriptor_sha256'] == self.pins[run_path],
                'EIGHTCAM_RUN_CLOCK_BINDING')
        require(run['catalog_sha256'] == settings['catalog_sha256'] == self.pins[CATALOG]
                == graph['camera_catalog_sha256'], 'EIGHTCAM_CATALOG_BINDING')
        cameras = {m['camera_id'] for m in source['sampling']['per_camera']}
        require(len(cameras) == 8 and cameras == set(run['camera_ids'])
                == {c['camera_id'] for c in catalog['cameras']}, 'EIGHTCAM_CAMERA_SCOPE')
        interval = 200_000
        require(run['fps'] == 5 and run['sample_count_per_camera'] == samples
                and all(m['index_interval_us'] == interval for m in source['sampling']['per_camera']),
                'EIGHTCAM_SAMPLING')
        by_camera = {camera: {} for camera in cameras}
        indexed = {(row['camera_id'], row['frame_index']): row['rgb_file_sha256']
                   for row in index.records}
        for entry in run['frames']:
            camera, frame = entry['camera_id'], entry['frame_index']
            relative = f'rgb/{self.run_id}/{camera}/{frame:06d}.png'
            digest = entry['sha256']
            require(camera in by_camera and 0 <= frame < samples and frame not in by_camera[camera]
                    and entry['source_time_us'] == frame * interval
                    and relative == entry['relative_path'] and self.pins.get(relative) == digest
                    == indexed.get((camera, frame)), 'EIGHTCAM_FRAME_BINDING')
            by_camera[camera][frame] = self.root / relative, digest
        require(len(indexed) == 8 * samples and all(len(frames) == samples for frames in by_camera.values()),
                'EIGHTCAM_FRAME_COVERAGE')
        return index, clock, settings, catalog, graph, (interval, by_camera, clock.clock_id)


def source_error_code(exc):
    """Publish a bounded reason for an optional bundle without exposing data or paths."""
    if isinstance(exc, OSError):
        return 'EIGHTCAM_SOURCE_IO'
    if type(exc) is ValueError:
        code = str(exc)
        if re.fullmatch(r'EIGHTCAM_[A-Z_]+', code) or code in {
            'BYTE_PIN_MISMATCH', 'CANONICAL_FILE_REQUIRED', 'OWNED_PATH_ESCAPE_OR_SYMLINK',
        }:
            return code
    return 'EIGHTCAM_SOURCE_INVALID'


def prepare_eightcam(root, *, required=True):
    try:
        return _prepare_eightcam(root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        if required:
            raise
        return None, source_error_code(exc)


def _prepare_eightcam(root):
    """Select exact read-only files from the checked-in #529 receipt."""
    if root is None:
        return None, 'ROOT_NOT_CONFIGURED'
    root = Path(root).absolute()
    require(root.resolve() == root, 'EIGHTCAM_CANONICAL_ROOT_REQUIRED')
    if not root.is_dir():
        return None, 'SAFE_BUNDLE_MISSING'
    entries = loads(RECEIPT.read_bytes())['files']
    metadata = set().union(*(metadata_for(label) for label in RUN_SPECS))
    prefixes = tuple(f"rgb/{spec['run_id']}/" for spec in RUN_SPECS.values())
    pins = {}
    for entry in entries:
        if not entry['relative_path'].startswith(BUNDLE_PREFIX):
            continue
        relative = entry['relative_path'][len(BUNDLE_PREFIX):]
        if relative not in metadata and not relative.startswith(prefixes):
            continue
        require(relative not in pins and len(entry['sha256']) == 64, 'EIGHTCAM_RECEIPT')
        path = owned_path(root, relative)
        if not path.is_file():
            return None, 'SAFE_BUNDLE_INCOMPLETE'
        pins[relative] = entry['sha256']
    require(len(pins) == sum(8 * spec['samples'] for spec in RUN_SPECS.values()) + len(metadata)
            and metadata <= pins.keys(),
            'EIGHTCAM_RECEIPT_SCOPE')
    return EightCamSource(root, pins), None
