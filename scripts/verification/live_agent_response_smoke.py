"""#675: bounded loopback inference from existing pinned synthetic PNGs; no truth input."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import time
import urllib.request
from PIL import Image


def request(path, data=None, binary=False):
    raw = data if binary else json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request('http://127.0.0.1:8791' + path, data=raw,
                                 headers={'Content-Type': 'application/octet-stream' if binary else 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    descriptor = a.root / 'rgb/E3-A1/rgb_index.json'
    raw = descriptor.read_bytes()
    records = [r for r in json.loads(raw)['records'] if r['frame_index'] == 0]
    frames, pins = [], []
    for r in records:
        data = (a.root / r['relative_path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == r['file_sha256']
        with Image.open(io.BytesIO(data)) as im:
            buf = io.BytesIO(); im.convert('RGB').save(buf, format='JPEG', quality=85)
        frames.append((r['camera_id'], buf.getvalue()))
        pins.append({'path': r['relative_path'], 'sha256': r['file_sha256']})
    def infer(tick):
        h = {'tick': tick, 't_capture_ms': tick * 500, 'available_cameras': [c for c, _ in frames],
             'frames': [{'cam': c, 'bytes': len(j)} for c, j in frames]}
        b = json.dumps(h).encode()
        return request('/infer', struct.pack('<I', len(b)) + b + b''.join(j for _, j in frames), True)
    session = request('/reset')['session_id']
    rows = [infer(0)]
    start = request('/track/start', {'session_id': session, 'color': 'red'})
    pick = None
    if start['mode'] == 'NEEDS_PICK':
        candidates = request('/track/candidates?color=red')['candidates']
        assert candidates, 'NO_PIXEL_COLOUR_CANDIDATE'
        pick = request('/track/pick', {'session_id': session, 'cand_id': candidates[0]['cand_id']})
    for tick in range(1, 16):
        rows.append(infer(tick))
        tr = rows[-1].get('tracking') or {}
        if tr.get('decision_source') == 'AGENT':
            break
        time.sleep(1)
    ok = rows[-1].get('tracking', {}).get('decision_source') == 'AGENT'
    receipt = {'scope': 'API_SMOKE_SYNTHETIC_PIXELS_NOT_RESEARCH', 'source_manifest_sha256':
               hashlib.sha256((a.root/'MANIFEST.json').read_bytes()).hexdigest(),
               'rgb_index_sha256': hashlib.sha256(raw).hexdigest(), 'frames': pins,
               'start': start, 'pick': pick, 'rows': rows, 'agent_response_verified': ok}
    a.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'agent_response_verified': ok, 'ticks': len(rows), 'last_tracking': rows[-1].get('tracking')}))
    assert ok, 'NO_AGENT_RESPONSE_IN_BOUNDED_SMOKE'


if __name__ == '__main__':
    main()
