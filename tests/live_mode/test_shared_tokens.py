"""#633: LIVE serves exactly the shared token asset, without exposing workbench files."""
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

from amidst.live_mode import server


def test_shared_token_routes_use_one_source_and_block_directory_traversal(tmp_path, monkeypatch):
    canonical = tmp_path / 'shared' / 'tokens.css'
    canonical.parent.mkdir()
    canonical.write_bytes(b':root{--accent:coral}')
    (canonical.parent / 'private.txt').write_text('must not be served')
    monkeypatch.setattr(server, 'SHARED_TOKENS', canonical)
    backend = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(SimpleNamespace(n6=False)))
    worker = threading.Thread(target=backend.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    worker.start()
    def get(path):
        connection = HTTPConnection('127.0.0.1', backend.server_port)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()
    try:
        for path in ('/shared/tokens.css', '/src/tokens.css', '/shared/tokens.css?v=633'):
            status, mime, body = get(path)
            assert status == 200 and mime == 'text/css' and body == canonical.read_bytes()
        canonical.write_bytes(b':root{--accent:blue}')
        assert get('/shared/tokens.css')[2] == canonical.read_bytes()
        for path in ('/shared/private.txt', '/shared/../private.txt', '/shared/%2e%2e/private.txt', '/shared/tokens.css/../private.txt'):
            assert get(path)[0] == 404
        canonical.unlink()
        assert get('/shared/tokens.css')[0] == 404  # no silent fallback to the stale LIVE mirror
    finally:
        backend.shutdown()
        backend.server_close()
        worker.join(timeout=2)
