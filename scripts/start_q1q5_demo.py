"""Start a pinned LOCAL replay on loopback; never start or download a model."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import webbrowser

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.demo_launcher import bind_demo, prepare_demo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--live', action='store_true', help='Request live mode; unselected runtime falls back to pinned replay')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    try:
        app, receipt = prepare_demo(args.bundle.resolve(), args.manifest_sha256, args.state_root.resolve(),
                                    live=args.live, ui_root=repo / 'frontend/workbench-v2')
        with bind_demo(app, args.port) as http:
            url = f'http://127.0.0.1:{http.server_port}/workbench-v2/?recording={receipt["recording_id"]}'
            receipt.update(url=url, pid=os.getpid(), owner_nonce=secrets.token_hex(16))
            (args.state_root / 'DEMO_SERVER.json').write_text(json.dumps(receipt, indent=2) + '\n')
            print(json.dumps(receipt, sort_keys=True), flush=True)
            if args.live:
                print('fallback：錄製重播（live runtime 未選定；未呼叫模型）', flush=True)
            if not args.no_open:
                webbrowser.open(url)
            try:
                http.serve_forever(poll_interval=.2)
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc)}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
