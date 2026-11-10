"""Local static r005 review server: exact routes on 127.0.0.1 only."""

from __future__ import annotations

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'src'))
from amidst.paths import locate_artifact  # noqa: E402
RGB = locate_artifact('d127-418-office-expanded-r005-preview-v2/rgb')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_routes():
    manifest = json.loads((HERE / 'manifest.json').read_bytes())
    if manifest['original_rgb_copied'] is not False or manifest['original_rgb_directory'] != str(RGB):
        raise ValueError('SOURCE_SCOPE_MISMATCH')
    routes = {}
    for name, media in [('index.html', 'text/html; charset=utf-8'),
                        ('style.css', 'text/css; charset=utf-8'),
                        ('app.js', 'text/javascript; charset=utf-8'),
                        ('data.json', 'application/json; charset=utf-8')]:
        info = manifest['artifacts'][name]
        raw = (HERE / name).read_bytes()
        if len(raw) != info['bytes'] or sha(raw) != info['sha256']:
            raise ValueError(f'LOCAL_ARTIFACT_PIN_MISMATCH:{name}')
        routes['/' if name == 'index.html' else '/' + name] = (raw, media)
    data = json.loads(routes['/data.json'][0])
    pins = manifest['camera_frame_sha256']
    if (len(pins) != 6 or set(pins) != {c['camera_id'] for c in data['cameras']}
            or data['coverage_basis'] != 'NOT_EVALUATED' or data['threshold'] != 0.3):
        raise ValueError('PREVIEW_SCOPE_MISMATCH')
    if not RGB.is_dir() or RGB.resolve() != RGB or RGB.is_symlink():
        raise ValueError('RGB_ROOT_NOT_CANONICAL')
    for camera, pin in pins.items():
        if not camera.isascii() or not camera.replace('_', '').isalnum():
            raise ValueError('CAMERA_ID_REJECTED')
        routes[f'/rgb/{camera}.png'] = (RGB / f'{camera}.png', 'image/png', pin)
    return routes


def serve(port):
    routes = load_routes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                self.send_error(403)
                return
            item = routes.get(self.path)
            if item is None:
                self.send_error(404)
                return
            if isinstance(item[0], Path):
                path, kind, pin = item
                if path.is_symlink() or not path.is_file() or path.parent != RGB:
                    self.send_error(404)
                    return
                raw = path.read_bytes()
                if sha(raw) != pin:
                    self.send_error(409)
                    return
            else:
                raw, kind = item
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            self.send_error(405)

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as http:
        print(f'Local r005 review: http://127.0.0.1:{port}/', flush=True)
        http.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    try:
        serve(args.port)
    except KeyboardInterrupt:
        pass
