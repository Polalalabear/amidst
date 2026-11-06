"""Start verified P1 engineering bundle on loopback using Python 3.12+ only."""
import argparse
import json
import secrets
import sys
import webbrowser
from pathlib import Path

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
if sys.platform == "win32":
    try:
        import zoneinfo
        zoneinfo.ZoneInfo("UTC")
    except Exception:
        import site
        site.main()
if sys.version_info<(3,12):raise SystemExit('需要 Python 3.12 以上；不會自動安裝套件。')  # noqa: UP036 -- standalone bundle launcher also runs outside this project
from amidst.q1q5.p1_workbench import P1, server


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True,type=Path);p.add_argument('--manifest-sha256')
    p.add_argument('--state-root',type=Path);p.add_argument('--runtime',type=Path);p.add_argument('--runtime-sha256')
    p.add_argument('--tracking-scope',type=Path);p.add_argument('--tracking-scope-sha256')
    p.add_argument('--current-ui',action='store_true',help='Serve this checkout workbench-v2 with the current backend')
    p.add_argument('--port',type=int,default=0);p.add_argument('--no-open',action='store_true')
    a=p.parse_args(argv)
    if a.tracking_scope and not a.current_ui:p.error('--tracking-scope requires --current-ui')
    root=a.bundle.resolve()
    pin=a.manifest_sha256 or (root/'MANIFEST.sha256').read_text().strip()
    parent=a.state_root.parent if a.state_root else root/'STATE';parent.mkdir(exist_ok=True)
    state=a.state_root or parent/('run-'+secrets.token_hex(6))
    repo=Path(__file__).resolve().parents[1]
    tracking_scope = a.tracking_scope.resolve() if a.tracking_scope else None
    runtime = a.runtime.resolve() if a.runtime else None
    app=P1(root,pin,state,runtime=runtime,runtime_pin=a.runtime_sha256,
        tracking_scope=tracking_scope,tracking_scope_pin=a.tracking_scope_sha256,
        ui_root=repo/'frontend/workbench-v2' if a.current_ui else None)
    with server(app,a.port) as http:
        url=f'http://127.0.0.1:{http.server_port}/workbench-v2/?mode=review'
        if not a.tracking_scope and app.spec.get('default_recording_id'):url+='&recording='+app.spec['default_recording_id']
        receipt={'url':url,'pid':__import__('os').getpid(),'owner_nonce':secrets.token_hex(16),'manifest_sha256':pin,
            'source_commit':app.manifest['source_commit'],'source_kind':'SYNTHETIC','gt_read':False,
            'model_configured':bool(a.runtime),'provider_cancellation_confirmed':None,'state_root':str(state)}
        receipt.update(tracking_scope_sha256=a.tracking_scope_sha256,current_ui=a.current_ui)
        (state/'SERVER.json').write_text(json.dumps(receipt,indent=2)+'\n');print(url,flush=True)
        if not a.no_open:webbrowser.open(url)
        try:http.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:pass
    return 0


if __name__=='__main__':raise SystemExit(main())
