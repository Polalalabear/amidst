"""Pinned P1 launcher over shared QAPI and workbench-v2, Python stdlib only.

This adapter serves engineering RGB/indexes and exact recorded responses. It does
not render, detect, invent observations, or activate a model without explicit pins.
"""
import hashlib
import json
import mimetypes
import os
import secrets
import shutil
import stat
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

from amidst.q1q5.api import QAPI, APIError, RecordingStore, from_environment
from amidst.q1q5.dynamic_rgb import load_dynamic_rgb
from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.store import canonical_hash


def require(ok, code):
    if not ok:raise ValueError(code)


def local(root, ref):
    require(isinstance(ref,str) and ref and not ref.startswith('/') and '\\' not in ref,'RELATIVE_PATH_REQUIRED')
    parts=PurePosixPath(ref).parts
    require(all(p not in {'.','..'} for p in parts),'PATH_ESCAPE')
    p=root.joinpath(*parts)
    require(p.resolve().is_relative_to(root) and not any(x.is_symlink() for x in [p,*p.parents] if x.is_relative_to(root)),'PATH_ESCAPE')
    return p


def verify_bundle(root, expected_manifest_sha256):
    require(root.is_absolute() and root.resolve()==root,'CANONICAL_BUNDLE_REQUIRED')
    raw=read_pinned(root/'MANIFEST.json',expected_manifest_sha256);m=strict_json(raw)
    require(m['schema_version']=='q-demo.p1-bundle-manifest.v1' and len(m['files'])<=4096,'BUNDLE_MANIFEST')
    size=0
    for name,pin in m['files'].items():
        p=local(root,name);require(p.is_file() and p.stat().st_size==pin['bytes'],'BUNDLE_SIZE_MISMATCH')
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        require(h.hexdigest()==pin['sha256'],'BUNDLE_HASH_MISMATCH');size+=p.stat().st_size
    require(size==m['total_bytes'],'BUNDLE_TOTAL_MISMATCH')
    return m


def binary(path,pin):
    path=Path(path)
    require(path.is_absolute() and path.resolve()==path and path.suffix=='.png','CANONICAL_PNG_REQUIRED')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno());require(stat.S_ISREG(info.st_mode) and info.st_size<=16_777_216,'RGB_SIZE_OR_TYPE')
        raw=f.read(16_777_217)
    require(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==pin,'RGB_PIN_MISMATCH')
    return raw


def public_png(raw):
    """Same text-chunk/CRC policy as the shared renderer RGB bridge."""
    signature=b'\x89PNG\r\n\x1a\n';require(raw.startswith(signature),'RGB_PNG_INVALID')
    out=bytearray(signature);offset=8;chunks=0;ended=False
    while offset<len(raw):
        require(offset+12<=len(raw),'RGB_PNG_INVALID');size=int.from_bytes(raw[offset:offset+4],'big');end=offset+size+12
        require(end<=len(raw),'RGB_PNG_INVALID');kind=raw[offset+4:offset+8];payload=raw[offset+8:end-4]
        require(zlib.crc32(kind+payload)==int.from_bytes(raw[end-4:end],'big'),'RGB_PNG_INVALID')
        require(chunks!=0 or (kind==b'IHDR' and size==13),'RGB_PNG_INVALID')
        if kind not in {b'tEXt',b'iTXt',b'zTXt'}:out.extend(raw[offset:end])
        chunks+=1;offset=end
        if kind==b'IEND':
            require(size==0 and offset==len(raw),'RGB_PNG_INVALID');ended=True;break
    require(ended,'RGB_PNG_INVALID');return bytes(out)


class RGB:
    def __init__(self,path,pin,authorize):
        self.run=load_dynamic_rgb(path,pin,strict_json(read_pinned(path,pin)),binary=binary,require=require)
        self.authorize=authorize;self.grants={};self.requests=0;self.media_served=0

    def call(self,action,payload):
        require(action=='synced_frames','RGB_ACTION');self.authorize(payload['session_ref'],payload['scene_id'])
        m=self.run.manifest;stamp=round(payload['t_s']*1000000)
        require((payload['scene_id'],payload['run_id'])==(m['scene_id'],m['run_id']) and stamp>=0,'RGB_SCOPE')
        cameras=payload['camera_ids'];require(cameras and len(set(cameras))==len(cameras) and set(cameras)<=self.run.camera_ids,'RGB_CAMERA_SCOPE')
        frame=stamp//50000;tiles=[];now=time.monotonic();self.grants={k:v for k,v in self.grants.items() if v['expires']>now}
        require(len(self.grants)+len(cameras)<=4096,'MEDIA_GRANT_LIMIT')
        for camera in cameras:
            row=self.run.rgb_record(camera,frame)
            tile={'camera_id':camera,'frame_ref':None,'media_url':None,'status':'OUT_OF_RANGE'}
            if row is not None:
                raw=self.run.read_rgb(camera,frame);token=secrets.token_urlsafe(32)
                self.grants[token]={'session_ref':payload['session_ref'],'camera':camera,'frame':frame,'pin':row['file_sha256'],'expires':now+60}
                tile.update(status='READY',frame_ref=f"frame:{m['run_id']}:{camera}:{frame}",frame_index=frame,timestamp_s=frame/20,
                    file_sha256=row['file_sha256'],served_sha256=hashlib.sha256(public_png(raw)).hexdigest(),media_token_ttl_s=60,
                    media_url='/api/controlled_scene_media?token='+token)
            tiles.append(tile)
        self.requests+=1
        result={'schema_version':'controlled-scene.synced-frames.v1','status':'READY','data_origin':'SYNTHETIC',
            'rgb_source_kind':'SYNTHETIC_GENERATED_RGB','identity_verdict':'UNCONFIRMED','agent_used':False,
            'resolved_scope':{'scene_id':m['scene_id'],'run_id':m['run_id']},'clock_id':m['clock_id'],'t_s':payload['t_s'],
            'tiles':tiles,'provenance':{'gt_read':False,'producer':'q1q5-p1-rgb'}}
        result['output_sha256']=canonical_hash({**result,'tiles':[{**t,'media_url':None} for t in tiles]});return result

    def media(self,token):
        grant=self.grants.get(token);require(grant is not None and time.monotonic()<grant['expires'],'MEDIA_TOKEN_INVALID')
        self.authorize(grant['session_ref'],self.run.manifest['scene_id'])
        row=self.run.rgb_record(grant['camera'],grant['frame']);require(row['file_sha256']==grant['pin'],'MEDIA_PIN_MISMATCH')
        self.media_served+=1;return public_png(self.run.read_rgb(grant['camera'],grant['frame']))


class P1:
    def __init__(self,root,manifest_pin,state_root,*,runtime=None,runtime_pin=None):
        self.root=root;self.manifest=verify_bundle(root,manifest_pin);self.sessions={};self.spec=strict_json((root/'BUNDLE.json').read_bytes())
        require(self.spec['schema_version']=='q-demo.p1-bundle.v1' and self.spec['source_kind']=='SYNTHETIC','BUNDLE_SCOPE')
        require(not state_root.exists() and state_root.parent.is_dir(),'NEW_STATE_REQUIRED')
        require(shutil.disk_usage(state_root.parent).free>=8*1024**3,'DISK_BELOW_8_GIB');state_root.mkdir()
        self.state_root=state_root;self.started=time.monotonic()
        registry_path=local(root,self.spec['registry_ref']);config=strict_json(registry_path.read_bytes())
        require(config['data_root']=='.' and config['recording_root'] is None and config['recordings']==[],'RELATIVE_REGISTRY_REQUIRED')
        config['data_root']=str(registry_path.parent);config['content_sha256']=canonical_hash(config,exclude=('content_sha256',))
        p=state_root/'registry.json';p.write_text(json.dumps(config,sort_keys=True,separators=(',',':'))+'\n')
        os.environ['AMIDST_Q1Q5_REGISTRY']=str(p);os.environ['AMIDST_Q1Q5_REGISTRY_SHA256']=hashlib.sha256(p.read_bytes()).hexdigest()
        for key in ['AMIDST_Q1Q5_OLLAMA_RUNTIME','AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256']:os.environ.pop(key,None)
        require(bool(runtime)==bool(runtime_pin),'RUNTIME_PIN_REQUIRED')
        if runtime:
            read_pinned(runtime,runtime_pin);os.environ['AMIDST_Q1Q5_OLLAMA_RUNTIME']=str(runtime);os.environ['AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256']=runtime_pin
        self.rgb=RGB(local(root,self.spec['rgb_ref']),self.spec['rgb_file_sha256'],self.authorize)
        api=from_environment(self.rgb,root/'app')
        store=RecordingStore(local(root,self.spec['recordings_ref']),repo_root=root/'app',max_bytes=16_777_216)
        self.api=QAPI(list(api.runs.values()),max_responses=128,max_media_refs=4096,recording_store=store,recordings=self.spec['recordings'],rgb_api=self.rgb)
        (state_root/'recordings').mkdir();self.api.recording_store=RecordingStore(state_root/'recordings',repo_root=root/'app',max_bytes=16_777_216)
        for scene,run in self.api.runs:
            require((scene,run)==(self.rgb.run.manifest['scene_id'],self.rgb.run.manifest['run_id']),'REGISTRY_RGB_SCOPE')

    def bootstrap(self):
        value=self.api.bootstrap()
        for row in value['recordings']:
            row['switch_mode']=self.api.recordings[row['recording_id']][1]['request'].get('switch_mode')
        return value

    def authorize(self,token,scene,*,audit=False):
        require(token in self.sessions and scene in self.sessions[token],'FORBIDDEN_DATA_SCOPE')

    def call(self,action,payload):
        if action=='session':
            require(set(payload)=={'role'} and payload['role'] in {'research','reviewer','demo'},'SESSION_ROLE')
            token=secrets.token_urlsafe(32);self.sessions[token]={self.rgb.run.manifest['scene_id']}
            return {'session_ref':token,'role':payload['role']}
        return self.api.call(action,payload,self.authorize)

    def handler(self):
        app=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,body,content_type='application/json; charset=utf-8'):
                self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
            def valid_host(self):
                port=self.server.server_port;require(self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'},'LOOPBACK_HOST_REQUIRED')
            def do_GET(self):
                try:
                    self.valid_host();u=urlsplit(self.path)
                    if u.path in {'/return/','/return/index.html'}:return self.reply(200,(app.root/'RETURN/index.html').read_bytes(),'text/html; charset=utf-8')
                    if u.path=='/api/q_bootstrap':return self.reply(200,json.dumps(app.bootstrap()).encode())
                    if u.path=='/api/controlled_scene_media':
                        q=parse_qs(u.query);require(set(q)=={'token'} and len(q['token'])==1,'MEDIA_TOKEN_INVALID')
                        return self.reply(200,app.rgb.media(q['token'][0]),'image/png')
                    relative='index.html' if u.path in {'/','/workbench-v2/','/workbench-v2'} else u.path.removeprefix('/workbench-v2/')
                    require(u.path in {'/','/workbench-v2/','/workbench-v2'} or u.path.startswith('/workbench-v2/'),'STATIC_SCOPE')
                    p=local(app.root/'app/frontend/workbench-v2',relative)
                    require(p.suffix in {'.html','.mjs','.css','.json'} and p.is_file(),'STATIC_SCOPE')
                    return self.reply(200,p.read_bytes(),'text/javascript' if p.suffix=='.mjs' else mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
                except (ValueError,KeyError,OSError):return self.reply(403,b'{"error_code":"FORBIDDEN_DATA_SCOPE"}')
            def do_POST(self):
                try:
                    self.valid_host();require(self.headers.get('Origin') in {None,'http://'+self.headers['Host']} and self.headers.get('Sec-Fetch-Site')!='cross-site','ORIGIN_DENIED')
                    require(self.headers.get('Content-Type','').split(';')[0]=='application/json','JSON_REQUIRED')
                    size=int(self.headers.get('Content-Length','0'));require(0<size<=65536,'BODY_SIZE')
                    u=urlsplit(self.path);require(u.path.startswith('/api/') and not u.query,'API_SCOPE')
                    data=app.call(u.path.removeprefix('/api/'),strict_json(self.rfile.read(size)))
                    return self.reply(200,json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
                except APIError as e:return self.reply(e.status,json.dumps({'error_code':e.code}).encode())
                except (ValueError,KeyError,TypeError,OSError):return self.reply(403,b'{"error_code":"FORBIDDEN_DATA_SCOPE"}')
        return Handler


def server(app,port=0):return ThreadingHTTPServer(('127.0.0.1',port),app.handler())
