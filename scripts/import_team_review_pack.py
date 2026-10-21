"""Mechanical import of human returns. Never derive answers from system predictions."""
from __future__ import annotations
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess

from build_team_review_pack import (
    TEXT_COLUMNS, REVIEW_COLUMNS, TEXT_FILE, REVIEW_FILE, PackError,
    canonical, sha, safe_file, disk,
)


def read_csv(raw):
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        return reader.fieldnames or [],list(reader)
    except (UnicodeError,csv.Error) as exc:raise PackError('Invalid UTF-8 CSV') from exc


def import_pack(pack,*,manifest_sha256,output,text_csv=None,review_csv=None,annotations=None):
    pack=Path(pack).absolute();output=Path(output).absolute()
    raw_manifest=safe_file(pack,'MANIFEST.json').read_bytes()
    if sha(raw_manifest)!=manifest_sha256:raise PackError('Trusted MANIFEST pin mismatch')
    manifest=json.loads(raw_manifest)
    if manifest.get('schema_version')!='team-review-pack.v1':raise PackError('Unknown manifest schema')
    editable=manifest['editable_files']
    if set(editable)!={TEXT_FILE,REVIEW_FILE}:raise PackError('Unexpected editable files')
    # Editable CSV bytes are intentionally allowed to change. Immutable source
    # templates remain hash-checked, and locked columns are compared by ID.
    for name,digest in manifest['files'].items():
        if name not in editable and sha(safe_file(pack,name).read_bytes())!=digest:
            raise PackError('Immutable pack file SHA mismatch: '+name)
    for name,description in editable.items():
        template=description['template_ref']
        if manifest['files'].get(template)!=manifest['files'].get(name):raise PackError('Template binding mismatch')
    returns={TEXT_FILE:Path(text_csv).read_bytes() if text_csv else safe_file(pack,TEXT_FILE).read_bytes(),
             REVIEW_FILE:Path(review_csv).read_bytes() if review_csv else safe_file(pack,REVIEW_FILE).read_bytes()}
    parsed={};invalid=[]
    for name,columns in [(TEXT_FILE,TEXT_COLUMNS),(REVIEW_FILE,REVIEW_COLUMNS)]:
        headers,rows=read_csv(returns[name]);_,original=read_csv(safe_file(pack,editable[name]['template_ref']).read_bytes())
        key=columns[0];by_id={r[key]:r for r in original};seen=set();parsed[name]=[]
        if len(by_id)!=len(original):raise PackError('Duplicate frozen template ID')
        header_ok=headers==columns
        for index,row in enumerate(rows,2):
            rid=row.get(key)
            if rid not in by_id or rid in seen:raise PackError('Missing/unknown/duplicate returned ID')
            seen.add(rid)
            for col in editable[name]['locked_columns']:
                if col in headers and row.get(col)!=by_id[rid][col]:raise PackError('Immutable CSV field changed')
            if not header_ok or None in row:
                invalid.append({'file':name,'id':rid,'row':index,'status':'INVALID','reason':'CSV_COLUMNS_INVALID','submitted':row});continue
            parsed[name].append(row)
        if seen!=set(by_id):raise PackError('Returned CSV deleted frozen IDs')
    samples={r['sample_id']:r for r in manifest['samples']}
    if len(samples)!=len(manifest['samples']):raise PackError('Duplicate sample map')
    q4=[];queries=[];cases=[]
    for row in parsed[REVIEW_FILE]:
        rid=row[REVIEW_COLUMNS[0]];answer=row[REVIEW_COLUMNS[3]].strip()
        if answer not in {'T','F','不確定'}:
            invalid.append({'file':REVIEW_FILE,'id':rid,'status':'INVALID','reason':'ANSWER_MISSING_OR_INVALID','submitted':row});continue
        source=samples[rid]
        q4.append({'schema_version':'q4-tf-review.v1','sample_id':rid,'frame_ref':f"frame:{source['run_id']}:{source['camera_id']}:{source['frame_index']}",
                   'run_id':source['run_id'],'camera_id':source['camera_id'],'frame_index':source['frame_index'],
                   'rgb_file_sha256':source['rgb_file_sha256'],'prediction_sha256':source['prediction_sha256'],
                   'system_positive':source['system_positive'],'statement':row[REVIEW_COLUMNS[2]],'answer':answer,'notes':row[REVIEW_COLUMNS[4]],
                   'pilot':not manifest['evaluation_eligible'],'evaluation_eligible':manifest['evaluation_eligible']})
    annotation_raw=None;annotations_by_id={}
    if annotations:
        annotation_raw=Path(annotations).read_bytes()
        for line in annotation_raw.splitlines():
            a=json.loads(line)
            if not isinstance(a,dict) or not isinstance(a.get('id'),str) or a['id'] in annotations_by_id:raise PackError('Invalid/duplicate human annotation ID')
            annotations_by_id[a['id']]=a
        text_ids={r[TEXT_COLUMNS[0]] for r in parsed[TEXT_FILE]}
        if set(annotations_by_id)-text_ids:raise PackError('Annotation ID outside text return')
    q3_status={'PARSED','NEEDS_CLARIFICATION','UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','PARSE_FAILED','TIME_EXPRESSION_INVALID'}
    q1_status={'READY','NO_MATCH','PARTIAL','UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','OUT_OF_RANGE','UNKNOWN'}
    llm_keys={'schema_version','intent','class_term','color_term','time_literal','camera_terms','region_terms','needs_clarification','clarification_question'}
    for row in parsed[TEXT_FILE]:
        rid=row[TEXT_COLUMNS[0]];text=row[TEXT_COLUMNS[1]];a=annotations_by_id.get(rid)
        if (not text.strip() or row[TEXT_COLUMNS[2]] not in {'人','車','相機'} or row[TEXT_COLUMNS[7]] not in {'是','否'}
                or row[TEXT_COLUMNS[8]] not in {'找得到','找不到','不支援','超出時間','反問'}):
            invalid.append({'file':TEXT_FILE,'id':rid,'status':'INVALID','reason':'TEXT_FIELDS_MISSING_OR_INVALID','submitted':row});continue
        if not a or a.get('text')!=text:
            invalid.append({'file':TEXT_FILE,'id':rid,'status':'INVALID','reason':'PRECISE_HUMAN_ANNOTATION_REQUIRED','submitted':row});continue
        # These are supplied human annotations, not parser/search outputs. No
        # keywords, clock guesses, camera guesses, scores or expected boxes added.
        valid=False
        q3=a.get('q3')
        if isinstance(q3,dict):
            expected=q3.get('expected_llm_output');status=q3.get('expected_status');query=q3.get('expected_structured_query')
            if (isinstance(expected,dict) and set(expected)==llm_keys
                    and expected.get('schema_version')=='q-demo.q3-llm-output.v1'
                    and expected.get('intent') in {'FIND_CAMERAS','FIND_PERSON','EXPLAIN','UNSUPPORTED'}
                    and status in q3_status and isinstance(q3.get('category'),str)
                    and ((status=='PARSED' and isinstance(query,dict) and query.get('schema_version') in {'q-demo.q1-request.v1','q-demo.q2-request.v1'}) or (status!='PARSED' and query is None))):
                queries.append({'id':rid,'text':text,'category':q3['category'],'expected_llm_output':expected,'expected_status':status,'expected_structured_query':query,'notes':row[TEXT_COLUMNS[-1]]});valid=True
        q1=a.get('q1')
        if isinstance(q1,dict):
            core=q1.get('expected_response_core');request=q1.get('request')
            if (isinstance(core,dict) and {'status','reason','results','no_match_cameras','not_evaluated_cameras'}<=core.keys()
                    and core['status'] in q1_status and isinstance(request,dict) and request.get('schema_version')=='q-demo.q1-request.v1' and isinstance(q1.get('index_ref'),str)):
                cases.append({'id':rid,'description':text,'index_ref':q1['index_ref'],'request':request,'expected_response_core':core,'notes':row[TEXT_COLUMNS[-1]]});valid=True
        if not valid:invalid.append({'file':TEXT_FILE,'id':rid,'status':'INVALID','reason':'PRECISE_HUMAN_ANNOTATION_INVALID','submitted':row})
    if output.exists() or output.resolve()!=output:raise PackError('Refuse existing/noncanonical output')
    disk(output.parent);output.mkdir();(output.parent/(output.name+'.df-before.txt')).write_text(subprocess.check_output(['df','-k',str(output)],text=True))
    payloads={'queries_v1.jsonl':queries,'cases_v1.jsonl':cases,'q4_tf_review_v1.jsonl':q4,'invalid_rows.jsonl':invalid}
    output_hashes={}
    for name,rows in payloads.items():
        disk(output);data=b''.join(canonical(row)+b'\n' for row in sorted(rows,key=lambda r:(r.get('file',''),r.get('id',r.get('sample_id','')))))
        (output/name).write_bytes(data);output_hashes[name]=sha(data)
    report={'schema_version':'team-review-import.v1','pack_manifest_sha256':manifest_sha256,'pack_version':manifest['version'],'evaluation_eligible':manifest['evaluation_eligible'],
            'returned_files_sha256':{name:sha(raw) for name,raw in returns.items()},'human_annotations_sha256':sha(annotation_raw) if annotation_raw else None,
            'counts':{name:len(rows) for name,rows in payloads.items()},'output_files_sha256':output_hashes,
            'precise_annotations_schema_validation':'STRUCTURE_ONLY; full contract validation required by evaluation tools'}
    report['output_sha256']=sha(canonical(report));(output/'receipt.json').write_bytes(canonical(report)+b'\n')
    (output.parent/(output.name+'.df-after.txt')).write_text(subprocess.check_output(['df','-k',str(output)],text=True));disk(output)
    return report


def register_import(registry,report):
    registry=Path(registry);line='| '+report['output_sha256']+' | '+report['pack_version']+' | '+report['pack_manifest_sha256']+' | '+json.dumps(report['returned_files_sha256'],ensure_ascii=False,sort_keys=True)+' |\n'
    text=registry.read_text() if registry.exists() else '# Team review pack registry\n\n回收結果僅供評估端；PILOT 不進正式分母。\n\n| output_sha256 | version | MANIFEST SHA-256 | returned CSV SHA-256 |\n| --- | --- | --- | --- |\n'
    if report['output_sha256'] not in text:registry.write_text(text+line)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['pack','manifest-sha256','output','registry']:parser.add_argument('--'+key,required=True)
    for key in ['text-csv','review-csv','annotations']:parser.add_argument('--'+key)
    a=parser.parse_args();output=Path(a.output).absolute()
    if not output.is_relative_to((Path.home()/'amidst-artifacts').resolve()):raise PackError('LOCAL output must be under ~/amidst-artifacts')
    report=import_pack(a.pack,manifest_sha256=a.manifest_sha256,output=output,text_csv=a.text_csv,review_csv=a.review_csv,annotations=a.annotations)
    register_import(a.registry,report);print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
