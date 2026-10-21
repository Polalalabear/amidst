"""Mechanical pack tests using fake RGB and fake human returns, never a testset."""
import csv
import io
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from build_team_review_pack import (
    PackError,TEXT_COLUMNS,REVIEW_COLUMNS,TEXT_FILE,REVIEW_FILE,
    build_pack,csv_bytes,sha,
)
from import_team_review_pack import import_pack,register_import


def source(tmp_path):
    root=tmp_path/'source';samples=[]
    for i in range(4):
        raw=b'\x89PNG\r\n\x1a\nSYNTHETIC'+bytes([i]);p=root/'rgb/CAM'/f'frame_{i:06d}.png';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        samples.append({'run_id':'RUN_SYN','clock_id':'CLOCK_SYN','camera_id':'CAM','frame_index':i,'rgb_file_sha256':sha(raw),'polarity':i%2==0,'statement':'SYNTHETIC POSITIVE' if i%2==0 else 'SYNTHETIC NEGATIVE','prediction_ref':'prediction:SYNTHETIC','prediction_sha256':'b'*64})
    guide=tmp_path/'guide.md';guide.write_text('SYNTHETIC GUIDE')
    return dict(guide=guide,samples=samples,sources={'RUN_SYN':{'root':str(root),'clock_id':'CLOCK_SYN','source_sha256':'a'*64,'dataset':'A','scene_revision':'r003'}},sample_count=200,seed='SYNTHETIC',text_rows=1,version='v0-pilot',samples_sha256='c'*64)


def pack(tmp_path):
    args=source(tmp_path);p=tmp_path/'pack';manifest=build_pack(p,**args)
    return p,sha((p/'MANIFEST.json').read_bytes()),manifest


def edit_csv(path,columns,mutate):
    rows=list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    for row in rows:mutate(row)
    path.write_bytes(csv_bytes(columns,rows))


def fill(p):
    edit_csv(p/REVIEW_FILE,REVIEW_COLUMNS,lambda row:row.update({REVIEW_COLUMNS[3]:'T'}))
    edit_csv(p/TEXT_FILE,TEXT_COLUMNS,lambda row:row.update({TEXT_COLUMNS[1]:'SYNTHETIC',TEXT_COLUMNS[2]:'相機',TEXT_COLUMNS[7]:'是',TEXT_COLUMNS[8]:'反問'}))


def annotation(tmp_path):
    p=tmp_path/'annotations.jsonl';p.write_text(json.dumps({'id':'Q0001','text':'SYNTHETIC','q3':{'category':'SYNTHETIC','expected_llm_output':{'schema_version':'q-demo.q3-llm-output.v1','intent':'FIND_CAMERAS','class_term':None,'color_term':None,'time_literal':{'start':None,'end':None,'date':None},'camera_terms':[],'region_terms':[],'needs_clarification':True,'clarification_question':'SYNTHETIC'},'expected_status':'NEEDS_CLARIFICATION','expected_structured_query':None}})+'\n');return p


def test_deterministic_balanced_pack_reports_actual_shortfall(tmp_path):
    args=source(tmp_path);one=build_pack(tmp_path/'one',**args);two=build_pack(tmp_path/'two',**args)
    assert one==two
    assert one['sampling']=={'method':'sha256(seed,run,camera,frame,claim), balanced strata, no replacement','seed':'SYNTHETIC','requested':200,'actual':4,'positive':2,'negative':2,'shortfall':196}
    assert not one['evaluation_eligible']
    assert (tmp_path/'one/MANIFEST.json').read_bytes()==(tmp_path/'two/MANIFEST.json').read_bytes()
    assert set(one['files'])=={p.relative_to(tmp_path/'one').as_posix() for p in (tmp_path/'one').rglob('*') if p.is_file()}-{'MANIFEST.json'}


def test_valid_human_return_has_new_hash_and_reproducible_output(tmp_path):
    p,pin,m=pack(tmp_path);fill(p);a=annotation(tmp_path)
    one=import_pack(p,manifest_sha256=pin,output=tmp_path/'return1',annotations=a)
    two=import_pack(p,manifest_sha256=pin,output=tmp_path/'return2',annotations=a)
    assert one==two and one['counts']['queries_v1.jsonl']==1 and one['counts']['q4_tf_review_v1.jsonl']==4
    assert one['counts']['invalid_rows.jsonl']==0
    assert one['returned_files_sha256'][TEXT_FILE]!=m['files'][TEXT_FILE]
    assert not one['evaluation_eligible']
    registry=tmp_path/'registry.md';register_import(registry,one);before=registry.read_bytes();register_import(registry,one);assert registry.read_bytes()==before


def test_coarse_text_answer_never_becomes_precise_standard_answer(tmp_path):
    p,pin,_=pack(tmp_path);fill(p);r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned')
    assert r['counts']['queries_v1.jsonl']==0 and r['counts']['cases_v1.jsonl']==0
    assert 'PRECISE_HUMAN_ANNOTATION_REQUIRED' in (tmp_path/'returned/invalid_rows.jsonl').read_text()


@pytest.mark.parametrize('answer',['','yes','X','TRUE'])
def test_missing_or_invalid_tf_is_invalid_without_guessing(tmp_path,answer):
    p,pin,_=pack(tmp_path);fill(p);edit_csv(p/REVIEW_FILE,REVIEW_COLUMNS,lambda row:row.update({REVIEW_COLUMNS[3]:answer}))
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned')
    assert r['counts']['q4_tf_review_v1.jsonl']==0 and r['counts']['invalid_rows.jsonl']==5


def test_missing_answer_column_marks_rows_invalid(tmp_path):
    p,pin,_=pack(tmp_path)
    columns=[x for x in REVIEW_COLUMNS if x!=REVIEW_COLUMNS[3]]
    rows=list(csv.DictReader(io.StringIO((p/REVIEW_FILE).read_text(encoding='utf-8-sig'))))
    for row in rows:row.pop(REVIEW_COLUMNS[3])
    (p/REVIEW_FILE).write_bytes(csv_bytes(columns,rows))
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned')
    assert r['counts']['q4_tf_review_v1.jsonl']==0 and 'CSV_COLUMNS_INVALID' in (tmp_path/'returned/invalid_rows.jsonl').read_text()


@pytest.mark.parametrize('target',['image','template','locked','manifest'])
def test_hash_or_locked_field_tamper_refuses_entire_pack(tmp_path,target):
    p,pin,_=pack(tmp_path);fill(p)
    if target=='image':(p/'B_畫面審查/frames/S0001.png').write_bytes(b'WRONG')
    elif target=='template':(p/'templates/情境.csv').write_bytes(b'WRONG')
    elif target=='locked':edit_csv(p/REVIEW_FILE,REVIEW_COLUMNS,lambda row:row.update({REVIEW_COLUMNS[2]:'WRONG'}))
    else:(p/'MANIFEST.json').write_bytes((p/'MANIFEST.json').read_bytes()+b' ')
    with pytest.raises(PackError):import_pack(p,manifest_sha256=pin,output=tmp_path/'refused')
    assert not (tmp_path/'refused').exists()


def test_source_symlinks_hash_mismatch_and_missing_stratum_refused(tmp_path):
    args=source(tmp_path);args['samples']=args['samples'][:1]
    with pytest.raises(PackError):build_pack(tmp_path/'one',**args)
    args=source(tmp_path);args['samples'][0]['rgb_file_sha256']='0'*64
    with pytest.raises(PackError):build_pack(tmp_path/'two',**args)
    args=source(tmp_path);image=Path(args['sources']['RUN_SYN']['root'])/'rgb/CAM/frame_000000.png';backup=image.with_suffix('.backup');image.rename(backup);image.symlink_to(backup)
    with pytest.raises(PackError):build_pack(tmp_path/'three',**args)


def test_ids_cannot_be_duplicated_or_deleted(tmp_path):
    p,pin,_=pack(tmp_path);raw=(p/REVIEW_FILE).read_bytes();(p/REVIEW_FILE).write_bytes(raw+raw.splitlines(keepends=True)[1])
    with pytest.raises(PackError):import_pack(p,manifest_sha256=pin,output=tmp_path/'refused')
