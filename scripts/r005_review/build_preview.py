"""Build a local, bounded r005 static RGB review receipt. No image copies."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'src'))
from amidst.paths import locate_artifact  # noqa: E402
PROBE = locate_artifact('d129-464-r005-probe-20261105-a')
RGB = locate_artifact('d127-418-office-expanded-r005-preview-v2/rgb')
PR473 = '978bf6ce9e955700022af235b284aa5ff4c8a73f'
PR447 = '39b9c4323288cae8c52532277cdd6dc75b63a965'
def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pinned(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f'PIN_MISMATCH:{path.name}')
    return raw


def main() -> None:
    handoff = json.loads((PROBE / 'handoff_manifest.json').read_bytes())
    # Use the exact source pins in the delivery record. These remain separate
    # from the GitHub code heads and confer no approval on the frame contents.
    expected = {
        'report.json': handoff['report_sha256'],
        'raw_top300.jsonl': handoff['raw_top300_sha256'],
        'graph_contract/region_graph.json': handoff['graph_contract_sha256']['region_graph.json'],
    }
    report = json.loads(pinned(PROBE / 'report.json', expected['report.json']))
    raw_lines = pinned(PROBE / 'raw_top300.jsonl', expected['raw_top300.jsonl']).splitlines()
    graph = json.loads(pinned(PROBE / 'graph_contract/region_graph.json', expected['graph_contract/region_graph.json']))
    if (report['status'] != 'ENGINEERING_ONLY' or report['human_layout'] != 'SKIPPED_HUMAN_LAYOUT_ONLY'
            or graph['approval_status'] != 'DRAFT'
            or report['coverage_basis'] != 'NOT_EVALUATED' or report['human_approval_verified'] is not False
            or report['display_threshold'] != 0.3 or len(raw_lines) != 6
            or len(report['rows']) != 6 or len(graph['regions']) != 6):
        raise ValueError('UNEXPECTED_REVIEW_SCOPE')
    regions = [row['region_id'] for row in graph['regions']]
    if len(set(regions)) != 6:
        raise ValueError('DUPLICATE_REGIONS')
    raw_by_camera = {row['camera_id']: row for row in (json.loads(line) for line in raw_lines)}
    cameras = []
    for row in report['rows']:
        camera = row['camera_id']
        if camera not in raw_by_camera or '/' in camera or '\\' in camera:
            raise ValueError('UNDECLARED_CAMERA')
        source = raw_by_camera[camera]
        shown = [d for d in source['detections'] if d['score'] >= 0.3]
        if (row['shown'] != shown or row['shown_count'] != len(shown)
                or row['file_sha256'] != source['file_sha256']
                or source['image_size_px'] != [960, 540]):
            raise ValueError('DETECTION_REPORT_MISMATCH')
        image = RGB / f'{camera}.png'
        image_raw = pinned(image, row['file_sha256'])
        if image_raw[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('PNG_REQUIRED')
        cameras.append({'camera_id': camera, 'frame_sha256': row['file_sha256'],
                        'image_size_px': [960, 540], 'detections': shown,
                        'image_url': f'/rgb/{camera}.png'})
    if len({c['camera_id'] for c in cameras}) != 6 or sum(len(c['detections']) for c in cameras) != 33:
        raise ValueError('CAMERA_OR_CANDIDATE_COUNT')
    data = {'schema_version': 'local-r005-static-review.v1', 'scene_id': report['scene_id'],
            'source_pr_heads': {'473': PR473, '447': PR447},
            'report_sha256': expected['report.json'], 'raw_top300_sha256': expected['raw_top300.jsonl'],
            'region_graph_sha256': expected['graph_contract/region_graph.json'],
            'threshold': 0.3, 'coverage_basis': 'NOT_EVALUATED',
            'approval_status': 'DRAFT', 'regions': regions, 'cameras': cameras}
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    (HERE / 'data.json').write_bytes(raw)
    artifacts = {}
    for name in ('index.html', 'style.css', 'app.js', 'server.py', 'build_preview.py', 'data.json'):
        path = HERE / name
        artifacts[name] = {'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}
    manifest = {'schema_version': 'local-r005-review-artifacts.v1',
                'source_pr_heads': data['source_pr_heads'], 'source_report_sha256': data['report_sha256'],
                'source_raw_sha256': data['raw_top300_sha256'], 'source_region_graph_sha256': data['region_graph_sha256'],
                'original_rgb_directory': str(RGB),
                'original_rgb_copied': False,
                'camera_frame_sha256': {c['camera_id']: c['frame_sha256'] for c in cameras},
                'candidate_count_at_0_30': 33, 'legal_region_count': len(regions),
                'screenshots_directory': str(HERE / 'screenshots'), 'screenshots_count': 0,
                'artifacts': artifacts}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'cameras': len(cameras), 'candidates': 33, 'regions': regions,
                      'data_sha256': artifacts['data.json']['sha256']}))


if __name__ == '__main__':
    main()
