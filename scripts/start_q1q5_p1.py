"""Start verified P1 engineering bundle on loopback using Python 3.12+ only."""
import argparse
import json
import secrets
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
if sys.version_info<(3,12):raise SystemExit('需要 Python 3.12 以上；不會自動安裝套件。')  # noqa: UP036 -- standalone bundle launcher also runs outside this project
from amidst.q1q5.p1_workbench import P1, server


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True,type=Path);p.add_argument('--manifest-sha256')
    p.add_argument('--state-root',type=Path);p.add_argument('--runtime',type=Path);p.add_argument('--runtime-sha256')
    p.add_argument('--port',type=int,default=0);p.add_argument('--no-open',action='store_true')
    a=p.parse_args(argv);root=a.bundle.resolve()
    pin=a.manifest_sha256 or (root/'MANIFEST.sha256').read_text().strip()
    parent=root/'STATE';parent.mkdir(exist_ok=True)
    state=a.state_root or parent/('run-'+secrets.token_hex(6))
    app=P1(root,pin,state,runtime=a.runtime,runtime_pin=a.runtime_sha256)
    with server(app,a.port) as http:
        url=f'http://127.0.0.1:{http.server_port}/workbench-v2/?mode=review'
        if app.spec.get('default_recording_id'):url+='&recording='+app.spec['default_recording_id']
        receipt={'url':url,'pid':__import__('os').getpid(),'owner_nonce':secrets.token_hex(16),'manifest_sha256':pin,
            'source_commit':app.manifest['source_commit'],'source_kind':'SYNTHETIC','gt_read':False,
            'model_configured':bool(a.runtime),'provider_cancellation_confirmed':None,'state_root':str(state)}
        (state/'SERVER.json').write_text(json.dumps(receipt,indent=2)+'\n');print(url,flush=True)
        if not a.no_open:webbrowser.open(url)
        try:http.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass
    return 0


if __name__=='__main__':raise SystemExit(main())
