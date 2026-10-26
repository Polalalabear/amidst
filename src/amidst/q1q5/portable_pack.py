"""Build a bounded LOCAL P1 bundle from one Git commit and pinned safe inputs."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from amidst.q1q5.p1_workbench import binary
from amidst.q1q5.production_preflight import read_pinned, strict_json
from amidst.q1q5.store import canonical_hash

MODULES='api store graphs clock_mapping q3_parse q3_rules q1_search q5_controller linker candidates q4_evidence agent_tools q5_agent ollama_runtime llm_provider llm_guidance dynamic_rgb production_preflight p1_workbench'.split()
CRITERIA=[('AC1','一行啟動與離線錄製重播'),('AC2','三句查詢與選取起點'),('AC3','鏡頭／來源時間／真實目標框一致'),('AC4','同鏡頭框／A到B切鏡／找不到時誠實顯示'),('AC5','RULE_ONLY與AGENT錄製可選、timeout兜底如實標示'),('AC6','review有決策／候選／證據，demo不顯示內部判斷'),('AC7','replay原hash相同；#127全符合性仍待Claude，不能填PASS代替'),('AC8','GAP／UNKNOWN／身分未確認如實顯示')]


def safe_relative(value):
    if not isinstance(value,str) or not value:raise ValueError('RELATIVE_PATH_REQUIRED')
    p=Path(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value:raise ValueError('RELATIVE_PATH_REQUIRED')
    return p


def file_pin(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def scan_private_locators(root):
    """Inspect every text payload before sealing; never print the matched locator."""
    roots = tuple(('/' + part + '/').encode() for part in ('Users', 'home', 'private', 'tmp'))
    suffixes = {'.json', '.jsonl', '.txt', '.md', '.html', '.mjs', '.py', '.command', '.csv', '.css', '.sha256'}
    for path in root.rglob('*'):
        if path.is_file() and path.suffix in suffixes:
            raw = path.read_bytes()
            if any(prefix in raw for prefix in roots):
                raise ValueError('PRIVATE_LOCATOR_IN_PAYLOAD: ' + path.relative_to(root).as_posix())


def write_manifest(output, commit):
    files = {}
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.is_relative_to(output / 'STATE') or path.name in {'MANIFEST.json', 'MANIFEST.sha256'}:
            continue
        files[path.relative_to(output).as_posix()] = {'sha256': file_pin(path), 'bytes': path.stat().st_size}
    manifest = {'schema_version': 'q-demo.p1-bundle-manifest.v1', 'source_commit': commit,
                'files': files, 'total_bytes': sum(p['bytes'] for p in files.values()),
                'mutable_excluded': ['STATE/'],
                'return_policy': 'NEW_RETURN_FILES_ALLOWED_SHIPPED_TEMPLATES_IMMUTABLE',
                'formal_eligible': False, 'gt_read': False}
    write_json(output / 'MANIFEST.json', manifest)
    pin = file_pin(output / 'MANIFEST.json')
    (output / 'MANIFEST.sha256').write_text(pin + '\n', encoding='utf-8')
    return manifest, pin


def return_form():
    rows=''.join(f'<tr><td>{code}</td><td>{text}</td><td><select required data-code="{code}"><option value="">請選擇</option><option>T</option><option>F</option><option>不確定</option></select></td><td><textarea required placeholder="請寫看到的現象／理由，不填標準答案"></textarea></td></tr>' for code,text in CRITERIA)
    return '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>P1工程測試回交</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #aaa;padding:10px}textarea{min-width:300px;min-height:70px}button,input,select{font:inherit;padding:8px}</style><h1>P1 工程測試回交</h1><p>逐項操作後填T／F／不確定與理由。這不是正式研究成績；AC7仍需Claude的符合性報告。下載CSV後連同問題清單、截圖及完整資料夾或ZIP回交；保留原包。</p><form><label>姓名 <input id="name" required maxlength="32"></label><label>日期 <input id="date" type="date" required></label><table><tr><th>編號</th><th>檢查內容</th><th>結果</th><th>現象／理由</th></tr>'''+rows+'''</table><button>下載回交CSV</button></form><script>const d=new Date();document.querySelector('#date').value=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');document.querySelector('form').onsubmit=e=>{e.preventDefault();const name=document.querySelector('#name').value.replace(/[\\/:*?"<>|]/g,'_'),date=document.querySelector('#date').value,quote=v=>'"'+String(v).replaceAll('"','""')+'"';const rows=[['reviewer','date','criterion_id','result','reason']];for(const select of document.querySelectorAll('select'))rows.push([name,date,select.dataset.code,select.value,select.closest('tr').querySelector('textarea').value]);const raw='\\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\\r\\n')+'\\r\\n';const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([raw],{type:'text/csv;charset=utf-8'}));a.download='測試回報_'+name+'_'+date+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};</script></html>'''


def build(repo,commit,rgb,rgb_pin,registry,registry_pin,recordings,output):
    if output.exists() or output.resolve()!=output or not output.parent.is_dir():raise ValueError('NEW_CANONICAL_OUTPUT_REQUIRED')
    if shutil.disk_usage(output.parent).free<8*1024**3:raise ValueError('DISK_BELOW_8_GIB')
    subprocess.run(['git','cat-file','-e',commit+'^{commit}'],cwd=repo,check=True,capture_output=True)
    rgb_doc=strict_json(read_pinned(rgb,rgb_pin));reg=strict_json(read_pinned(registry,registry_pin))
    if rgb_doc['source_kind']!='SYNTHETIC' or rgb_doc['gt_read'] is not False:raise ValueError('ENGINEERING_RGB_ONLY')
    output.mkdir();code={}
    tree=subprocess.check_output(['git','ls-tree','-r','--name-only',commit],cwd=repo,text=True).splitlines()
    selected=['src/amidst/__init__.py','scripts/start_q1q5_p1.py']+['src/amidst/q1q5/'+n+'.py' for n in MODULES]
    selected += [n for n in tree if n.startswith('frontend/workbench-v2/') and n.endswith(('.mjs','.css','.html')) and '.test.' not in n and '/fixtures/' not in n]
    for n in sorted(set(selected)):
        raw=subprocess.check_output(['git','show',commit+':'+n],cwd=repo);dest=output/'app'/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);code[n]=hashlib.sha256(raw).hexdigest()
    def copy_pinned(source,pin,dest):
        raw=binary(source,pin) if source.suffix=='.png' else read_pinned(source,pin);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    rgb_root=output/'data/rgb';copy_pinned(rgb,rgb_pin,rgb_root/'rgb.json')
    copy_pinned(rgb.parent/safe_relative(rgb_doc['static_ref']),rgb_doc['static_file_sha256'],rgb_root/safe_relative(rgb_doc['static_ref']))
    for i,row in enumerate(rgb_doc['records']):
        ref=safe_relative(row['rgb_ref']);copy_pinned(rgb.parent/ref,row['file_sha256'],rgb_root/ref)
        if i%32==0 and shutil.disk_usage(output.parent).free<8*1024**3:raise ValueError('DISK_BELOW_8_GIB')
    data_root=Path(reg['data_root']);target=output/'data/registry'
    for pin in reg['documents'].values():
        ref=safe_relative(pin['path']);copy_pinned(data_root/ref,pin['file_sha256'],target/ref)
    reg['data_root']='.';reg['recording_root']=None;reg['recordings']=[];reg['content_sha256']=canonical_hash(reg,exclude=('content_sha256',))
    write_json(target/'registry.json', reg)
    entries=[]
    for item in recordings:
        source=Path(item['path']);raw=read_pinned(source,item['file_sha256']);doc=strict_json(raw)
        if doc['source_kind']!='SYNTHETIC' or doc['response']['identity_verdict']!='UNCONFIRMED':raise ValueError('ENGINEERING_RECORDING_ONLY')
        dest=output/'data/recordings'/source.name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(raw)
        entries.append({'recording_id':item['recording_id'],'file':source.name,'file_sha256':item['file_sha256']})
    spec={'schema_version':'q-demo.p1-bundle.v1','source_kind':'SYNTHETIC','formal_eligible':False,'gt_read':False,
          'rgb_ref':'data/rgb/rgb.json','rgb_file_sha256':rgb_pin,'registry_ref':'data/registry/registry.json',
          'recordings_ref':'data/recordings','recordings':entries,'default_recording_id':entries[0]['recording_id']}
    write_json(output/'BUNDLE.json', spec);write_json(output/'SOURCE.json', {'source_commit':commit,'files':code})
    (output/'start.command').write_text('#!/bin/zsh\nset -eu\nbundle_dir="${0:A:h}"\nexec /usr/bin/env python3 -S "$bundle_dir/app/scripts/start_q1q5_p1.py" --bundle "$bundle_dir" "$@"\n', encoding='utf-8');os.chmod(output/'start.command',0o755)
    readme='''這份工作內容
這是8秒／20fps工程場景P1測試，檢查操作與畫面，不是正式r004成績。RGB與RT-DETR索引固定；身分未確認，GAP不補框。需Python3.12以上，不需torch/Ollama，不會安裝依賴。

要提交項目
開啟RETURN/index.html，填姓名、日期、AC1–AC8的T／F／不確定與理由，下載RETURN/測試回報_<姓名>_YYYY-MM-DD.csv。另附問題／不確定／未完成項目與截圖，以及完整資料夾或ZIP。保留原包；不要把空白或未測項當T。D83：P1回交表只供人工閱讀、不補匯入器、不進正式指標；不要送入r004 importer。

操作
macOS雙擊start.command或在此資料夾執行./start.command。啟動重驗MANIFEST並開啟預設RULE_ONLY錄製，按播放。GAP保留RGB背景、不畫目標框；切鏡時間以該錄製的真實觀測為準。多鏡頭模式標示目前鏡頭。錄製選單可選AGENT_SEQUENTIAL，模型是否成功或逾時兜底以該錄製的model_calls、fallback_reason與agent_used實際數據為準；播放不會重跑模型。
三句查詢：哪些鏡頭拍到人13:00:00到13:00:08；哪些鏡頭拍到車13:00:00到13:00:08；哪些鏡頭拍到紅衣人13:00:00到13:00:08。預設RULE_ONLY，點播放片段或設為Q2起點。零結果照實看。審核mode=review顯示決策／候選／證據；移除mode可看Demo。播放量測面板提供實際frame/RAF/buffering與cache數字，物理顯示fps=null。用Ctrl-C關閉本次terminal服務，STATE保留啟動收據。
可選重新跑Qwen：只限已有已核定runtime/模型的操作者，執行python3 -S app/scripts/start_q1q5_p1.py --bundle . --runtime <本地runtime.json> --runtime-sha256 <sha>；維持D65，不下載權重。Windows未實測，不提供start.bat。

不要改
不要改app/data/BUNDLE/SOURCE/MANIFEST；用RETURN/index.html下載新的具名CSV；不要覆寫包內回交樣板，另存問題與截圖。STATE是本機啟動輸出，不是推論輸入。GT／producer／人員標記不在本包。不要把播放成功或replay hash相同當#127全符合性PASS：AC7仍待Claude對當前產品的完整符合性複核，正式G4／RGB／索引／人工成績未完成。
'''
    (output/'README.txt').write_text(readme, encoding='utf-8')
    returns=output/'RETURN';returns.mkdir();(returns/'index.html').write_text(return_form(), encoding='utf-8')
    with (returns/'測試回報_請填姓名_YYYY-MM-DD.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['reviewer','date','criterion_id','result','reason']);writer.writerows(['','',code,'',''] for code,_ in CRITERIA)
    scan_private_locators(output)
    manifest,pin=write_manifest(output,commit)
    files=manifest['files']
    return {'source_commit':commit,'manifest_sha256':pin,'payload_files':len(files),'payload_bytes':manifest['total_bytes'],
        'total_files':sum(p.is_file() for p in output.rglob('*')),'total_bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),'raw_rgb_files':len(rgb_doc['records']),
        'recordings':len(entries),'model_weights_included':False,'windows_tested':False,'formal_eligible':False,'gt_read':False}
