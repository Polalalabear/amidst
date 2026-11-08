"""LOCAL MIME/format adapter around the unmodified #408 P1 recorded workbench."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from build_proxies import public_png,read_pin,MIN_FREE
import shutil
p=argparse.ArgumentParser();p.add_argument('--checkout',type=Path,required=True);p.add_argument('--proxies',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--port',type=int,default=8782);a=p.parse_args()
repo=a.checkout.resolve();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
if head!='eb10d4c62ce09a765488cdd0548cfdd3abfd5109' or subprocess.check_output(['git','status','--porcelain'],cwd=repo):raise SystemExit('EXACT_CLEAN_SOURCE_REQUIRED')
if shutil.disk_usage(a.state.parent).free<MIN_FREE:raise SystemExit('DISK_BELOW_8_GIB')
manifest=json.loads(read_pin(a.proxies/'manifest.json',a.manifest_sha256));rows={(r['camera_id'],r['frame_index']):r for r in manifest['rows'] if r['case']=='B-05b'}
sys.path.insert(0,str(repo/'src'))
from amidst.q1q5.p1_workbench import P1
from amidst.q1q5.store import canonical_hash
app=P1(a.bundle,'6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7',a.state,ui_root=repo/'frontend/workbench-v2')
local=threading.local()
class Proxy:
 def __init__(self,base):self.base=base;self.formats={}
 def __getattr__(self,name):return getattr(self.base,name)
 def call(self,action,payload):
  doc=self.base.call(action,payload);fmt=getattr(local,'format','png')
  for tile in doc['tiles']:
   if tile['status']!='READY':continue
   token=tile['media_url'].split('token=',1)[1];grant=self.base.grants[token];row=rows[(grant['camera'],grant['frame'])]
   self.formats[token]=fmt;tile['served_sha256']=row['png_public_sha256'] if fmt=='png' else row['proxies'][fmt]['sha256']
  doc.pop('output_sha256',None);doc['output_sha256']=canonical_hash({**doc,'tiles':[{**t,'media_url':None} for t in doc['tiles']]});return doc
 def media(self,token):
  original=self.base.media(token);grant=self.base.grants[token];row=rows[(grant['camera'],grant['frame'])];fmt=self.formats[token]
  if fmt=='png':
   result=public_png(original)
   if hashlib.sha256(result).hexdigest()!=row['png_public_sha256']:raise ValueError('PUBLIC_PNG_PIN')
   return result
  info=row['proxies'][fmt];return read_pin(a.proxies/info['relative_path'],info['sha256'])
app.rgb=Proxy(app.rgb);app.api.rgb_api=app.rgb
Handler=app.handler();old_reply=Handler.reply;old_get=Handler.do_GET;old_post=Handler.do_POST
original_js=(repo/'frontend/workbench-v2/q-playback.mjs').read_bytes();old="new Blob([bytes],{type:'image/png'})"
if original_js.decode().count(old)!=1:raise SystemExit('EXACT_MIME_ADAPTER_SOURCE')
patched_js=original_js.decode().replace(old,"new Blob([bytes],{type:response.headers.get('content-type')})").encode()
def reply(self,status,body,content_type='application/json; charset=utf-8'):
 if status==200 and urlsplit(self.path).path.endswith('/q-playback.mjs'):body=patched_js
 if status==200 and content_type=='image/png':
  if body.startswith(b'\xff\xd8'):content_type='image/jpeg'
  elif body.startswith(b'RIFF') and body[8:12]==b'WEBP':content_type='image/webp'
 return old_reply(self,status,body,content_type)
def request_format(self):
 try:
  ref=urlsplit(self.headers.get('Referer',''));fmt=parse_qs(ref.query).get('format',['png'])[0]
  if ref.netloc and ref.netloc!=f'127.0.0.1:{a.port}':raise ValueError('SAME_ORIGIN')
  if fmt not in {'png','jpeg','webp'}:raise ValueError('FORMAT')
  local.format=fmt
 except ValueError:local.format='png'
def get(self):request_format(self);return old_get(self)
def post(self):request_format(self);return old_post(self)
Handler.reply=reply;Handler.do_GET=get;Handler.do_POST=post
print(json.dumps({'url':f'http://127.0.0.1:{a.port}/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938&format=png','source_head':head,'original_q_playback_sha256':hashlib.sha256(original_js).hexdigest(),'mime_adapter_sha256':hashlib.sha256(patched_js).hexdigest(),'proxy_manifest_sha256':a.manifest_sha256,'scope':'LOCAL PLAYBACK_ONLY MIME adapter; source checkout unchanged'}),flush=True)
with ThreadingHTTPServer(('127.0.0.1',a.port),Handler) as server:server.serve_forever()
