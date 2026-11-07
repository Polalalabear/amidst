"""Start only this task's independent pinned loopback previews; never merge or stop another server."""
from pathlib import Path
import errno,json,subprocess,time,urllib.request,urllib.error,shutil
ROOT=Path(__file__).resolve().parent
import argparse
p=argparse.ArgumentParser();p.add_argument('--python',required=True);args=p.parse_args()
PYTHON=args.python
SERVICES=[
 {'name':'452 SYNTHETIC core','probe':'http://127.0.0.1:8765/__preview/health','url':'http://127.0.0.1:8765/workbench-v2/','field':'source_head','expected':'088252833665a4bca9fcfbf31597b4bb296fb549','command':['/opt/homebrew/bin/node','/private/tmp/amidst-d131-tooling/preview-server.mjs','--source=/private/tmp/amidst-d128-419','--port=8765']},
 {'name':'442 ACTUAL D124 RGB','probe':'http://127.0.0.1:8770/health','url':'http://127.0.0.1:8770/?run=A4-1','field':'head','expected':'62a8979632d800e9ac6d23fc29789e56a11550bc','command':['/opt/homebrew/bin/node','/private/tmp/amidst-d131-442-viewer/server.mjs']},
 {'name':'447/473 r005 review','probe':'http://127.0.0.1:8769/data.json','url':'http://127.0.0.1:8769/','field':'report_sha256','expected':'0915d54d585fcbd8e89575bf1ab43dec0ae3b8e85839b8e59704fa9d03b6b021','command':[PYTHON,'/private/tmp/amidst-d131-464-review/server.py','--port','8769']},
]
def status(s):
 try:
  with urllib.request.urlopen(s['probe'],timeout=2) as r:d=json.load(r)
 except urllib.error.URLError as e:
  if isinstance(e.reason,ConnectionRefusedError) or getattr(e.reason,'errno',None)==errno.ECONNREFUSED:return False
  raise
 if d.get(s['field'])!=s['expected']:raise SystemExit('Port is occupied by a different source; left untouched: '+s['name'])
 return True
if shutil.disk_usage(ROOT).free<8*1024**3:raise SystemExit('Disk below 8 GiB; no startup')
for s in SERVICES:
 if not status(s):
  log=(ROOT/('preview-'+s['name'].split()[0]+'.log')).open('ab')
  cmd=s['command'];cmd[0]=shutil.which('node') if cmd[0].endswith('/node') else cmd[0]
  subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True,env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','LANG':'zh_TW.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
  for _ in range(100):
   if status(s):break
   time.sleep(.5)
  else:raise SystemExit('Startup not ready; inspect task log: '+s['name'])
 print(s['name']+': '+s['url'],flush=True)
print('B4-1: http://127.0.0.1:8770/?run=B4-1',flush=True)
