"""Deterministic review-pack builder. Input claims must be frozen system outputs.

No model, GT, script, question authoring or answer generation is performed here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

TEXT_COLUMNS = ['編號','使用者會說的話','想找什麼(人/車/相機)','顏色','開始時間','結束時間','鏡頭或區域','系統該反問嗎(是/否)','預期結果(找得到/找不到/不支援/超出時間/反問)','備註']
REVIEW_COLUMNS = ['樣本編號','圖檔','系統說法(例：這格有紅衣人／這格有車／這格沒有人)','答案(T/F/不確定)','備註']
TEXT_FILE = 'A_文字情境/情境.csv'
REVIEW_FILE = 'B_畫面審查/審查表.csv'
LOCKED = {TEXT_FILE: TEXT_COLUMNS[:1], REVIEW_FILE: REVIEW_COLUMNS[:3]}


class PackError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_bytes(columns,rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def relative(value):
    if not isinstance(value,str):raise PackError('Unsafe pack/source relative path')
    p=Path(value)
    if (not isinstance(value,str) or not value or p.is_absolute() or p.as_posix()!=value
            or '..' in p.parts or any(x.lower() in {'gt','private','private_evaluation','production','review_only'} for x in p.parts)):
        raise PackError('Unsafe pack/source relative path')
    return p


def safe_file(root,value):
    p=Path(root)/relative(value)
    if Path(root).resolve()!=Path(root).absolute() or any(x.is_symlink() for x in [p,*p.parents] if x!=x.parent):
        raise PackError('Symlinked source/pack is forbidden')
    if not p.is_file():raise PackError('Missing regular file')
    return p


def disk(root):
    if shutil.disk_usage(root).free < 8*1024**3:raise PackError('DISK_BELOW_8_GIB')


def build_pack(output,*,guide,samples,sources,sample_count,seed,text_rows=60,version='v0-pilot',samples_sha256):
    output=Path(output).absolute();guide=Path(guide)
    if output.exists():raise PackError('Refuse to overwrite a pack')
    if type(sample_count) is not int or sample_count<2 or sample_count%2:raise PackError('Even sample count required')
    if type(text_rows) is not int or text_rows<1:raise PackError('Text rows required')
    if version not in {'v0-pilot','v1'}:raise PackError('Unknown pack version')
    if output.resolve()!=output:raise PackError('Output must be canonical')
    disk(output.parent)
    guide_raw=guide.read_bytes();pools={True:[],False:[]};seen=set()
    required={'run_id','clock_id','camera_id','frame_index','rgb_file_sha256','polarity','statement','prediction_ref','prediction_sha256'}
    for row in samples:
        if set(row)!=required or type(row['polarity']) is not bool or type(row['frame_index']) is not int or row['frame_index']<0:
            raise PackError('Malformed frozen system claim')
        if row['run_id'] not in sources:raise PackError('Run not explicitly registered')
        reg=sources[row['run_id']]
        if reg['clock_id']!=row['clock_id']:raise PackError('Clock mismatch')
        if version=='v0-pilot' and reg.get('dataset') not in {'A','B1'}:raise PackError('PILOT requires A/B1 registration')
        if version=='v1' and reg.get('scene_revision')!='r004':raise PackError('Formal pack requires r004')
        for name in ['camera_id','run_id','clock_id','statement','prediction_ref']:
            if not isinstance(row[name],str) or not row[name] or row[name].startswith(('=','+','-','@','/')):raise PackError('Unsafe/missing claim text')
        if '/' in row['camera_id'] or '\\' in row['camera_id']:raise PackError('Invalid camera ID')
        key=(row['run_id'],row['camera_id'],row['frame_index'],row['statement'])
        if key in seen:raise PackError('Duplicate sample')
        seen.add(key)
        filename=f"rgb/{row['camera_id']}/frame_{row['frame_index']:06d}.png"
        source=safe_file(Path(reg['root']).absolute(),filename)
        raw=source.read_bytes()
        if sha(raw)!=row['rgb_file_sha256'] or not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise PackError('RGB pin/PNG mismatch')
        # Claims and source references are opaque declarations; never infer the answer.
        stable=sha(canonical({'seed':seed,'key':key}))
        pools[row['polarity']].append((stable,row,source))
    n=min(sample_count//2,len(pools[True]),len(pools[False]))
    if n<1:raise PackError('Both positive and negative system-claim strata required')
    selected=sorted(sorted(pools[True],key=lambda x:x[0])[:n]+sorted(pools[False],key=lambda x:x[0])[:n],key=lambda x:x[0])
    output.mkdir()
    (output.parent/(output.name+'.df-before.txt')).write_text(subprocess.check_output(['df','-k',str(output)],text=True))
    def put(name,raw):
        disk(output);p=output/relative(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return p
    pilot='這是試填流程，結果不算正式成績，也不拿來調整系統。' if version=='v0-pilot' else '這是正式回收包；仍須你獨立判斷與評估端驗證。'
    put('README.md',f'''# 組員審查包 {version}

## 這份工作內容
{pilot} 這份包有 A 文字情境與 B 畫面判斷兩項。A 的句子由你自己想；B 只判斷同編號的圖能不能支持表上的說法。不是判斷追蹤好不好或是否同一人。

## 要提交項目
請另存 **CSV UTF-8**，放進 `RETURN/`：`情境_<姓名>_YYYY-MM-DD.csv`、`審查表_<姓名>_YYYY-MM-DD.csv`。保留原本欄名與編號，填姓名／日期在檔名。完成後把完整資料夾或ZIP交回使用者；不用Git、JSON或repo權限。

## 操作
1. 開 `A_文字情境/情境.csv`。想找什麼欄只填「人」「車」「相機」：跟一個人填人；查哪些鏡頭拍到某物填相機（物件名稱寫在原句）；查車可填車。不要把長句填進這個三選一欄。
2. 起訖時間照原話填，可用 `HH:MM:SS`；知道日期／時區才加 `YYYY-MM-DD`／`+08:00`，不知道不要猜。預期結果只用欄名五種值；缺影像依據、部分涵蓋或資料不足就留空並在備註說明「資料不足／待補」。不用從檔名、場景用途或劇情猜答案。文字由Claude轉精確格式，缺精確標註的列會待補，不是你要自行寫JSON。
3. 開 `B_畫面審查/審查表.csv`，用圖檔欄找同編號圖片。T=圖支持說法，F=圖反駁說法，不確定=看不清或資訊不足。負向說法也照此規則：「說沒有人」且圖上確實看不到人，才可能填T；不能因系統沒框就填T。有／沒有各選{n}格，這些是待審的說法，不是答案。
4. B只改「答案(T/F/不確定)」與備註。F／不確定請寫原因。先試存一次CSV UTF-8，重開核對欄位／中文字，再完成其餘。

## 不要改
不要改編號、圖檔名、系統說法、templates、MANIFEST或maintainers內容；不要改圖、加框、找劇本或人物設定。未看到的東西留未知，不推斷盲區路線、真實身分或物理通行。這是另版補件，不要求重交已完成的舊工作。
'''.encode())
    put('RETURN/README.txt','只放另存的CSV UTF-8回交檔：情境_<姓名>_YYYY-MM-DD.csv、審查表_<姓名>_YYYY-MM-DD.csv。原表、欄名與固定編號不要改。整包或ZIP交回使用者。\n'.encode())
    put('maintainers/Q1Q3_QUESTION_AUTHORING_GUIDE.md',guide_raw)
    put('B_畫面審查/判定規則.md',('''# 判定規則\n\n對「該張圖能否支持系統說法」填 T/F；看不清、太小、遮擋或模糊而無法判斷時填不確定。能清楚看到部分人體仍可審查「有人」，衣色看不到就不能替衣色說法填 T。負向「沒有」也要看圖，不能因模型沒框就填 T。不要判斷跨鏡頭是不是同一人、追得好不好、盲區路線或物理通行。\n\nT=你認為圖支持該說法；F=你認為圖反駁該說法；不確定=資訊不足。這是試用規則，正式抽樣與標註準則待審查。\n'''+pilot+'\n').encode())
    texts=[{TEXT_COLUMNS[0]:f'Q{i:04d}'} for i in range(1,text_rows+1)]
    text_raw=csv_bytes(TEXT_COLUMNS,texts);put(TEXT_FILE,text_raw);put('templates/情境.csv',text_raw)
    # Structural examples contain no authored questions or answers (D70).
    put('A_文字情境/範例.csv',csv_bytes(TEXT_COLUMNS,[{TEXT_COLUMNS[0]:f'格式示意{i}',TEXT_COLUMNS[1]:'（此欄由組員填寫；不是題目）',TEXT_COLUMNS[-1]:'格式示意，不匯入評估'} for i in range(1,4)]))
    rows=[];sample_map=[]
    for i,(_,row,source) in enumerate(selected,1):
        disk(output);sid=f'S{i:04d}';frame=f'frames/{sid}.png';raw=source.read_bytes()
        if sha(raw)!=row['rgb_file_sha256']:raise PackError('Source RGB changed during packaging')
        put('B_畫面審查/'+frame,raw)
        rows.append({REVIEW_COLUMNS[0]:sid,REVIEW_COLUMNS[1]:frame,REVIEW_COLUMNS[2]:row['statement']})
        sample_map.append({'sample_id':sid,'run_id':row['run_id'],'clock_id':row['clock_id'],'camera_id':row['camera_id'],'frame_index':row['frame_index'],'source_sha256':sources[row['run_id']]['source_sha256'],'rgb_file_sha256':row['rgb_file_sha256'],'system_positive':row['polarity'],'prediction_ref':row['prediction_ref'],'prediction_sha256':row['prediction_sha256']})
    review_raw=csv_bytes(REVIEW_COLUMNS,rows);put(REVIEW_FILE,review_raw);put('templates/審查表.csv',review_raw)
    files={f.relative_to(output).as_posix():sha(f.read_bytes()) for f in sorted(output.rglob('*')) if f.is_file() and not f.name.startswith('df-')}
    manifest={'schema_version':'team-review-pack.v1','version':version,'evaluation_eligible':version=='v1','guide_sha256':sha(guide_raw),'system_claims_sha256':samples_sha256,'files':files,'editable_files':{TEXT_FILE:{'template_ref':'templates/情境.csv','locked_columns':LOCKED[TEXT_FILE]},REVIEW_FILE:{'template_ref':'templates/審查表.csv','locked_columns':LOCKED[REVIEW_FILE]}},'sampling':{'method':'sha256(seed,run,camera,frame,claim), balanced strata, no replacement','seed':seed,'requested':sample_count,'actual':2*n,'positive':n,'negative':n,'shortfall':sample_count-2*n},'samples':sample_map}
    put('MANIFEST.json',canonical(manifest)+b'\n')
    (output.parent/(output.name+'.df-after.txt')).write_text(subprocess.check_output(['df','-k',str(output)],text=True));disk(output)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['output','guide','claims','claims-sha256','sources']:parser.add_argument('--'+key,required=True)
    parser.add_argument('--samples',type=int,default=200);parser.add_argument('--seed',required=True);parser.add_argument('--version',choices=['v0-pilot','v1'],default='v0-pilot');a=parser.parse_args()
    raw=Path(a.claims).read_bytes()
    if sha(raw)!=a.claims_sha256:raise PackError('System claims pin mismatch')
    output=Path(a.output).absolute();allowed=(Path.home()/'amidst-artifacts').resolve()
    if not output.is_relative_to(allowed):raise PackError('LOCAL output must be under ~/amidst-artifacts')
    result=build_pack(output,guide=a.guide,samples=[json.loads(x) for x in raw.splitlines()],sources=json.loads(Path(a.sources).read_text()),sample_count=a.samples,seed=a.seed,version=a.version,samples_sha256=a.claims_sha256)
    print(json.dumps({'output':str(output),'manifest_sha256':sha((output/'MANIFEST.json').read_bytes()),'sampling':result['sampling']},ensure_ascii=False))


if __name__=='__main__':main()
