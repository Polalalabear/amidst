"""Start independent pinned previews from the user's persistent LOCAL delivery."""
from pathlib import Path
import argparse, errno, json, os, shutil, subprocess, sys, time
import urllib.request, urllib.error

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path.home()/'amidst-artifacts/d131-previews')
    parser.add_argument('--python',default=sys.executable)
    args=parser.parse_args();root=args.root.absolute()
    if root.is_symlink() or root.resolve()!=root or not root.is_dir():raise SystemExit('Canonical existing preview root required')
    if shutil.disk_usage(root).free<8*1024**3:raise SystemExit('Disk below 8 GiB; no startup')
    node=shutil.which('node')
    if not node:raise SystemExit('Existing Node executable required')
    services=[
      dict(name='452 SYNTHETIC core',probe='http://127.0.0.1:8765/__preview/health',url='http://127.0.0.1:8765/workbench-v2/',pins={'source_head':'088252833665a4bca9fcfbf31597b4bb296fb549','source_checkout':str(root/'checkouts/pr452')},command=[node,str(root/'tooling/preview-server.mjs'),'--source='+str(root/'checkouts/pr452'),'--port=8765']),
      dict(name='442 ACTUAL D124 RGB',probe='http://127.0.0.1:8770/health',url='http://127.0.0.1:8770/?run=A4-1',pins={'head':'62a8979632d800e9ac6d23fc29789e56a11550bc','source_checkout':str(root/'checkouts/pr442')},command=[node,str(root/'tooling/d124_event_viewer.mjs'),'--checkout='+str(root/'checkouts/pr442'),'--bundle='+str(Path.home()/'amidst-artifacts/r004-cx7r-20261104-01a19f8b/bundle/safe_bundle')]),
      dict(name='447/473 r005 review',probe='http://127.0.0.1:8769/__preview/health',url='http://127.0.0.1:8769/',pins={'report_sha256':'0915d54d585fcbd8e89575bf1ab43dec0ae3b8e85839b8e59704fa9d03b6b021','source_directory':str(root/'r005-review')},command=[args.python,str(root/'r005-review/server.py'),'--port','8769']),
    ]
    def status(service):
        try:
            with urllib.request.urlopen(service['probe'],timeout=2) as response:data=json.load(response)
        except urllib.error.URLError as error:
            if isinstance(error.reason,ConnectionRefusedError) or getattr(error.reason,'errno',None)==errno.ECONNREFUSED:return False
            raise SystemExit('Port is not the expected persistent preview; left untouched: '+service['name'])
        if any(data.get(k)!=v for k,v in service['pins'].items()):raise SystemExit('Port is occupied by a different source/location; left untouched: '+service['name'])
        return True
    (root/'logs').mkdir(exist_ok=True)
    for service in services:
        if not status(service):
            with (root/'logs'/('preview-'+service['name'].split()[0]+'.log')).open('ab') as log:
                subprocess.Popen(service['command'],stdout=log,stderr=log,start_new_session=True,env={'PATH':os.defpath+':/opt/homebrew/bin','LANG':'zh_TW.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
            for _ in range(100):
                if status(service):break
                time.sleep(.5)
            else:raise SystemExit('Startup not ready; inspect own log: '+service['name'])
        print(service['name']+': '+service['url'],flush=True)
    print('B4-1: http://127.0.0.1:8770/?run=B4-1',flush=True)
if __name__=='__main__':main()
