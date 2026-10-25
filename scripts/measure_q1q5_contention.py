"""Explicit local engineering measurement, never imported by product startup.

Read-only pinned preview RGB/official detector; no GT, downloads or rendering.
RSS, Ollama reported model bytes and system page counters are separate measures.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import URLError

MODEL='qwen3:1.7b-q4_K_M'
PIN='8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7'

def require(ok,msg):
    if not ok:raise ValueError(msg)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.write('\n')

def load_config(path,pin):
    path=Path(path);require(path.is_absolute() and path.resolve()==path and sha(path)==pin,'Config pin/path mismatch')
    d=json.loads(path.read_text());require(d['threads']==2 and d['seed']==7 and len(d['images'])==8,'Bounded detector profile required')
    for row in d['images']:
        p=Path(row['path']);require(p.resolve()==p and p.is_file() and sha(p)==row['sha256'],'RGB pin mismatch')
    return d

def disk(root):
    raw=subprocess.check_output(['df','-k',str(root)],text=True)
    return raw,int(raw.splitlines()[-1].split()[3])

def detector(config,out):
    from amidst.q1q5.detection_index import OfficialRTDetrR18
    from PIL import Image
    import resource
    t=time.monotonic();m=OfficialRTDetrR18(Path(config['source_root']),Path(config['weights']),source_hashes=config['source_hashes'],seed=config['seed'],threads=config['threads'])
    images=[]
    for row in config['images']:
        with Image.open(row['path']) as image:images.append(image.convert('RGB'))
    save(out/'detector-loaded.json',{'load_s':time.monotonic()-t,'metadata':m.metadata,'images':config['images'],'file_io_excluded_from_forward':True})
    # Explicit warmup is excluded from steady forward numbers, included in resource trace.
    m(images[0]);(out/'detector-ready').write_text('ready')
    while not (out/'start').exists():time.sleep(.02)
    n=0
    with (out/'detector.jsonl').open('x') as f:
        while not (out/'stop').exists():
            require(disk(out)[1]>=8*1024*1024,'STOP_BELOW_8_GIB')
            begin=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_SELF);pred=m(images[n%len(images)]);cpu1=resource.getrusage(resource.RUSAGE_SELF)
            row={'index':n,'start_monotonic':begin,'elapsed_ms':(time.monotonic()-begin)*1000,'cpu_s':cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,'camera_id':config['images'][n%8]['camera_id'],'returned_queries':len(pred)}
            f.write(json.dumps(row)+'\n');f.flush();n+=1
    for image in images:image.close()

class API:
    def __init__(self,url):
        from amidst.q1q5.llm_provider import LocalHTTPTransport
        self.base=LocalHTTPTransport(url).base_url;self.opener=build_opener(ProxyHandler({}))
    def call(self,path,payload=None,timeout=3):
        raw=None if payload is None else json.dumps(payload,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
        req=Request(self.base+path,data=raw,headers={'Content-Type':'application/json'})
        with self.opener.open(req,timeout=timeout) as f:return json.loads(f.read(1048577))
    def verify(self):
        matches=[x for x in self.call('/api/tags')['models'] if x['name']==MODEL]
        require(len(matches)==1 and matches[0]['digest']==PIN,'Selected model pin drift')
        require(all(x['name']==MODEL and x['digest']==PIN for x in self.call('/api/ps')['models']),'Another model is active')

def page_stats(raw):
    page=int(re.search(r'page size of (\d+) bytes',raw).group(1));values={}
    for key,value in re.findall(r'^([^:\n]+):\s+(\d+)\.',raw,re.M):values[key.strip().strip('"')]=int(value)
    return page,values

def sample(api,worker):
    raw=subprocess.check_output(['vm_stat'],text=True);page,values=page_stats(raw)
    swap=subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True)
    used=float(re.search(r'used = ([\d.]+)M',swap).group(1))*1024**2
    pressure=subprocess.check_output(['memory_pressure','-Q'],text=True)
    percent=int(re.search(r'free percentage: (\d+)%',pressure).group(1))
    processes=[]
    for line in subprocess.check_output(['ps','-ax','-o','pid=,ppid=,rss=,comm='],text=True).splitlines():
        parts=line.strip().split(None,3)
        if len(parts)==4:processes.append({'pid':int(parts[0]),'ppid':int(parts[1]),'rss_bytes':int(parts[2])*1024,'comm':parts[3]})
    ollama={p['pid'] for p in processes if Path(p['comm']).name=='ollama'}
    own=[p for p in processes if p['pid'] in ollama or p['ppid'] in ollama or p['pid'] in {worker,os.getpid()}]
    return {'monotonic':time.monotonic(),'vm_page_size':page,'vm_pages':values,'swap_used_bytes':used,
        'memory_pressure_free_pct':percent,'memory_pressure_pct_is_not_free_ram':True,'processes':own,'ollama_running':api.call('/api/ps')['models']}

def make_requests(config,profile):
    from amidst.q1q5.llm_provider import generation_request
    rows=[]
    for task in ['q3','q5']:
        old=json.loads(Path(config[task+'_trial']).read_text());args=old['provider_events'][0]['request']
        template=args['template'];prompt=args['prompt']
        if profile=='guided':
            root=Path(__file__).resolve().parents[1]
            template=(root/'configs/q1q5/prompts'/(task+('_parse_v2.txt' if task=='q3' else '_agent_v2.txt'))).read_text()
            if task=='q3':
                suffix=args['prompt'][len(args['template'])+1:];catalog,user=suffix.split('\nUSER_TEXT=',1)
                closed=json.loads(catalog[len('CLOSED_CATALOG='):]);closed.update(config.get('q3_aliases',{}))
                prompt=template+'\nCLOSED_CATALOG='+json.dumps(closed,ensure_ascii=True,sort_keys=True)+'\nUSER_TEXT='+user
            else:
                from amidst.q1q5.llm_guidance import workflow
                payload=json.loads(args['prompt'][len(args['template'])+1:]);payload['workflow']=workflow(payload['context'],{},[])
                prompt=template+'\n'+json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True)
        path,wire=generation_request(MODEL,prompt,template,{'temperature':0,'seed':7})
        rows.append({'task':task,'path':path,'wire':wire,'caller_prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()})
    return rows

def qwen_calls(api,requests,out):
    events=[]
    for repeat in range(3):
        for item in requests:
            if (out/'stop').exists():return events
            api.verify();start=time.monotonic();result=None;error=None
            try:
                result=api.call(item['path'],item['wire'],30);api.verify()
                require(result.get('model')==MODEL and result.get('done') is True and result.get('done_reason')=='stop','Invalid envelope')
            except (TimeoutError,URLError):error='PROVIDER_TIMEOUT_OR_NETWORK'
            except ValueError:error='INVALID_RESPONSE'
            event={'repeat':repeat,'task':item['task'],'start_monotonic':start,'elapsed_ms':(time.monotonic()-start)*1000,'error':error,'envelope':result,'wire_request':item['wire'],'caller_prompt_sha256':item['caller_prompt_sha256']}
            save(out/(item['task']+'-'+str(repeat)+'.json'),event);events.append(event)
    return events

def phase(api,config,config_path,config_pin,root,name,profile):
    out=root/name;out.mkdir(mode=0o700);(out/'df-before.txt').write_text(disk(root)[0]);require(disk(root)[1]>=8*1024*1024,'STOP_BELOW_8_GIB')
    worker=None;log=None;events=[];started=time.monotonic();future=None;pool=None
    try:
        if name in {'detector-only','concurrent'}:
            log=(out/'detector.stderr.txt').open('x');worker=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker','--config',str(config_path),'--config-sha256',config_pin,'--output',str(out)],stderr=log,stdout=log)
        # Resource trace includes loading, with stage markers for the steady subset.
        with (out/'resources.jsonl').open('x') as f:
            while worker and not (out/'detector-ready').exists():
                require(worker.poll() is None and time.monotonic()-started<60,'Detector failed to load; see log')
                f.write(json.dumps(sample(api,worker.pid))+'\n');f.flush();time.sleep(.5)
            steady=time.monotonic();(out/'start').write_text(str(steady))
            if name in {'qwen-only','concurrent'}:
                pool=ThreadPoolExecutor(max_workers=1);future=pool.submit(qwen_calls,api,make_requests(config,profile),out)
            stop_reason=None
            while True:
                row=sample(api,worker.pid if worker else None);f.write(json.dumps(row)+'\n');f.flush()
                if disk(root)[1]<8*1024*1024:stop_reason='DISK_BELOW_8_GIB'
                if row['memory_pressure_free_pct']<10:stop_reason='MEMORY_PRESSURE_FREE_LT_10'
                if row['swap_used_bytes']-config['initial_swap_used_bytes']>2*1024**3:stop_reason='SWAP_GROWTH_GT_2_GIB'
                if worker and worker.poll() is not None:stop_reason='DETECTOR_EXITED'
                if time.monotonic()-steady>200:stop_reason='PHASE_WALL_LIMIT'
                if stop_reason:break
                if time.monotonic()-steady>=30 and (future is None or future.done()):break
                time.sleep(.5)
            (out/'stop').write_text(stop_reason or 'complete')
            if future:events=future.result(timeout=35)
            if worker:worker.wait(timeout=15)
        require(stop_reason is None,'Measurement stopped: '+str(stop_reason))
        save(out/'PHASE.json',{'phase':name,'profile':profile,'steady_start_monotonic':steady,'steady_end_monotonic':time.monotonic(),'steady_s':time.monotonic()-steady,'detector_pid':worker.pid if worker else None,'qwen_calls':len(events),'detector_pacing':'SATURATED_NO_SLEEP' if worker else None,'minimum_phase_s':30,'rt_detr_concurrent':name=='concurrent','repeats_are_same_mechanical_input':True})
    finally:
        (out/'stop').write_text('complete-or-error')
        if worker and worker.poll() is None:
            try:worker.wait(timeout=15)
            except subprocess.TimeoutExpired:worker.terminate();worker.wait(timeout=5)
        if pool:pool.shutdown(wait=True)
        if log:log.close()
        (out/'df-after.txt').write_text(disk(root)[0])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--profile',choices=['baseline','guided']);p.add_argument('--worker',action='store_true');args=p.parse_args()
    config=load_config(args.config,args.config_sha256)
    if args.worker:return detector(config,args.output)
    require(args.profile is not None and args.output.is_absolute() and args.output.resolve()==args.output and not args.output.exists(),'New canonical output and explicit profile required')
    args.output.mkdir(mode=0o700);api=API(config['base_url']);api.verify();require(api.call('/api/ps')['models']==[],'Shared runner must start idle')
    try:
        save(args.output/'PROTOCOL.json',{'profile':args.profile,'config_file_sha256':args.config_sha256,'script_sha256':sha(__file__),'rt_detr_device':'cpu','threads':2,'input_size_px':[640,640],'model':MODEL,'model_digest':PIN,'rt_detr_rgb_is_preview_only':True,'calls_diagnostic_30s_not_product_budget':True,'no_RSS_VRAM_sum':True})
        load=api.call('/api/generate',{'model':MODEL,'prompt':'','stream':False,'keep_alive':'300s'},30);require(load.get('done_reason')=='load','Preload failed');save(args.output/'PRELOAD.json',load)
        for name in ['idle-loaded','detector-only','qwen-only','concurrent']:
            phase(api,config,args.config,args.config_sha256,args.output,name,args.profile)
    finally:
        api.verify();active=api.call('/api/ps')['models']
        if active:save(args.output/'RELEASE.json',{'response':api.call('/api/generate',{'model':MODEL,'prompt':'','stream':False,'keep_alive':0},10),'running_after':api.call('/api/ps')})
    print('MEASUREMENT_COMPLETE',args.profile,flush=True)

if __name__=='__main__':main()
