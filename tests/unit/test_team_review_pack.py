"""Mechanical pack tests using fake RGB and fake human returns, never a testset."""
import csv
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from build_team_review_pack import (
    REVIEW_COLUMNS,
    REVIEW_FILE,
    TEXT_COLUMNS,
    TEXT_FILE,
    PackError,
    build_pack,
    canonical,
    csv_bytes,
    sha,
)
from import_team_review_pack import import_pack, register_import


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


@pytest.mark.parametrize('target',['image','template','manifest'])
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


def test_member_instructions_and_maintainer_guide_are_separated(tmp_path):
    p,_,_=pack(tmp_path);text=(p/'README.md').read_text()
    for title in ['這份工作內容','要提交項目','操作','不要改']:
        assert '## '+title in text
    assert 'CSV UTF-8' in text and 'RETURN/' in text
    assert (p/'maintainers/Q1Q3_QUESTION_AUTHORING_GUIDE.md').read_text()=='SYNTHETIC GUIDE'
    assert not (p/'A_文字情境/說明.md').exists()


def test_locked_field_error_is_row_invalid_and_other_rows_survive(tmp_path):
    p,pin,_=pack(tmp_path);fill(p)
    path=p/REVIEW_FILE;rows=list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    rows[0][REVIEW_COLUMNS[2]]='ACCIDENTAL EDIT'
    path.write_bytes(csv_bytes(REVIEW_COLUMNS,rows))
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned',annotations=annotation(tmp_path))
    assert r['counts']['q4_tf_review_v1.jsonl']==3
    invalid=[json.loads(x) for x in (tmp_path/'returned/invalid_rows.jsonl').read_text().splitlines()]
    assert len(invalid)==1 and invalid[0]['reason']=='LOCKED_FIELD_CHANGED'
    assert invalid[0]['submitted'][REVIEW_COLUMNS[2]]=='ACCIDENTAL EDIT'


def test_every_return_row_keeps_pilot_flags_even_invalid_rows(tmp_path):
    p,pin,_=pack(tmp_path);fill(p)
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned')
    for name in r['output_files_sha256']:
        for line in (tmp_path/'returned'/name).read_text().splitlines():
            row=json.loads(line)
            assert row['pilot'] is True and row['evaluation_eligible'] is False


def test_supplied_annotation_outputs_keep_pilot_flags_and_do_not_generate_answers(tmp_path):
    p,pin,_=pack(tmp_path);fill(p);annotations=annotation(tmp_path)
    row=json.loads(annotations.read_text())
    row['q1']={'expected_response_core':{'status':'UNKNOWN','reason':None,'results':[],
                'no_match_cameras':[],'not_evaluated_cameras':[]},
               'request':{'schema_version':'q-demo.q1-request.v1'},'index_ref':'SYNTHETIC'}
    row['q1']['query_binding']={'request_sha256':sha(canonical(row['q1']['request'])),'query_sha256':'e'*64}
    row['q3']['expected_status']='PARSED'
    row['q3']['expected_structured_query']=row['q1']['request']
    row['q3']['expected_llm_output']['needs_clarification']=False
    row['q3']['expected_llm_output']['clarification_question']=None
    edit_csv(p/TEXT_FILE,TEXT_COLUMNS,lambda item:item.update({TEXT_COLUMNS[8]:'',TEXT_COLUMNS[-1]:'關鍵字=資料不足｜鏡頭=UNKNOWN｜說明=SYNTHETIC'}))
    annotations.write_text(json.dumps(row)+'\n')
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned',annotations=annotations)
    assert r['counts']['queries_v1.jsonl']==r['counts']['cases_v1.jsonl']==1
    for name in ['queries_v1.jsonl','cases_v1.jsonl']:
        result=json.loads((tmp_path/'returned'/name).read_text())
        assert result['pilot'] is True and result['evaluation_eligible'] is False


def test_non_utf8_error_explains_how_to_resave_without_creating_output(tmp_path):
    p,pin,_=pack(tmp_path)
    (p/REVIEW_FILE).write_bytes('繁體中文'.encode('big5'))
    with pytest.raises(PackError,match='CSV_UTF8_REQUIRED'):
        import_pack(p,manifest_sha256=pin,output=tmp_path/'refused')
    assert not (tmp_path/'refused').exists()


@pytest.mark.parametrize('value',[None,3,{}])
def test_nontext_relative_path_is_clean_pack_error(value):
    from build_team_review_pack import relative
    with pytest.raises(PackError):relative(value)


def test_formal_version_requires_explicit_r004_source_binding(tmp_path):
    args=source(tmp_path);args['version']='v1'
    with pytest.raises(PackError):build_pack(tmp_path/'refused',**args)
    args['sources']['RUN_SYN']['scene_revision']='r004'
    result=build_pack(tmp_path/'mechanical-v1',**args)
    assert result['evaluation_eligible'] is True


@pytest.mark.parametrize('answer',['F','不確定'])
def test_negative_or_uncertain_review_requires_a_reason(tmp_path,answer):
    p,pin,_=pack(tmp_path);fill(p)
    edit_csv(p/REVIEW_FILE,REVIEW_COLUMNS,lambda row:row.update({REVIEW_COLUMNS[3]:answer}))
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned')
    assert r['counts']['q4_tf_review_v1.jsonl']==0
    assert 'REASON_REQUIRED' in (tmp_path/'returned/invalid_rows.jsonl').read_text()


def test_extra_csv_cells_are_preserved_in_invalid_report_without_json_key_crash(tmp_path):
    p,pin,_=pack(tmp_path);fill(p)
    raw=(p/REVIEW_FILE).read_bytes().splitlines();raw[1]+=b',EXTRA'
    (p/REVIEW_FILE).write_bytes(b'\n'.join(raw)+b'\n')
    r=import_pack(p,manifest_sha256=pin,output=tmp_path/'returned',annotations=annotation(tmp_path))
    assert r['counts']['q4_tf_review_v1.jsonl']==3
    invalid=json.loads((tmp_path/'returned/invalid_rows.jsonl').read_text())
    assert invalid['extra_columns']==['EXTRA']


def d80_return(tmp_path,result,*,keyword=None,q3_status=None,q1_status=None):
    """Fake externally authored annotations, never real questions or answers."""
    p,pin,_=pack(tmp_path);fill(p);a_path=annotation(tmp_path)
    row=json.loads(a_path.read_text())
    request={'schema_version':'q-demo.q1-request.v1','origin':'SYNTHETIC_EXTERNAL',
             'session_id':'SYNTHETIC_SESSION','cursor':'SYNTHETIC_CURSOR'}
    if q3_status is None:row.pop('q3')
    else:
        row['q3']['expected_status']=q3_status
        row['q3']['expected_structured_query']=request if q3_status=='PARSED' else None
        row['q3']['expected_llm_output']['needs_clarification']=q3_status=='NEEDS_CLARIFICATION'
        row['q3']['expected_llm_output']['clarification_question']='SYNTHETIC' if q3_status=='NEEDS_CLARIFICATION' else None
    if q1_status is not None:
        row['q1']={'index_ref':'SYNTHETIC','request':request,
                   'expected_response_core':{'status':q1_status,'reason':None,'results':[],
                                             'no_match_cameras':[],'not_evaluated_cameras':[]},
                   'query_binding':{'request_sha256':sha(canonical({k:v for k,v in request.items() if k!='origin'})),
                                    'query_sha256':'f'*64}}
    a_path.write_text(json.dumps(row)+'\n')
    notes='關鍵字='+keyword+'｜鏡頭=UNKNOWN｜說明=SYNTHETIC' if keyword else ''
    edit_csv(p/TEXT_FILE,TEXT_COLUMNS,lambda item:item.update({TEXT_COLUMNS[8]:result,TEXT_COLUMNS[-1]:notes}))
    return p,pin,a_path


def run_d80(tmp_path,p,pin,a_path):
    output=tmp_path/'returned'
    report=import_pack(p,manifest_sha256=pin,output=output,annotations=a_path)
    rows={name:[json.loads(line) for line in (output/name).read_text().splitlines()]
          for name in report['output_files_sha256']}
    return report,rows


@pytest.mark.parametrize('keyword,q3,q1',[
    ('部分涵蓋','PARSED','PARTIAL'),('資料不足','PARSED','UNKNOWN'),
    ('時間無效','TIME_EXPRESSION_INVALID',None),('解析失敗','PARSE_FAILED',None),
    ('只測解析','PARSED',None),
])
def test_d80_each_blank_keyword_accepts_only_supplied_matching_annotation(tmp_path,keyword,q3,q1):
    p,pin,a=d80_return(tmp_path,'',keyword=keyword,q3_status=q3,q1_status=q1)
    report,rows=run_d80(tmp_path,p,pin,a)
    assert rows['invalid_rows.jsonl']==[]
    assert report['counts']['queries_v1.jsonl']==1
    assert report['counts']['cases_v1.jsonl']==int(q1 is not None)
    assert report['query_binding_source']=='EVALUATION_OWNER_PER_D80'
    assert rows['queries_v1.jsonl'][0]['notes'].startswith('關鍵字='+keyword+'｜')


@pytest.mark.parametrize('keyword,q3,q1',[
    ('部分涵蓋','PARSED','READY'),('資料不足','PARSED','PARTIAL'),
    ('時間無效','NEEDS_CLARIFICATION',None),('解析失敗','NEEDS_CLARIFICATION',None),
    ('只測解析','PARSED','READY'),
])
def test_d80_each_blank_keyword_contradiction_rejects_entire_row(tmp_path,keyword,q3,q1):
    p,pin,a=d80_return(tmp_path,'',keyword=keyword,q3_status=q3,q1_status=q1)
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='CSV_ANNOTATION_STATUS_MISMATCH'


@pytest.mark.parametrize('result,q3,q1',[
    ('找得到','PARSED','READY'),('找不到','PARSED','NO_MATCH'),('超出時間','PARSED','OUT_OF_RANGE'),
    ('反問','NEEDS_CLARIFICATION',None),('不支援','UNSUPPORTED_CLASS',None),
    ('不支援','UNSUPPORTED_CONDITION',None),
])
def test_d80_original_five_values_keep_closed_status_mapping(tmp_path,result,q3,q1):
    p,pin,a=d80_return(tmp_path,result,q3_status=q3,q1_status=q1)
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['invalid_rows.jsonl']==[]
    assert len(rows['queries_v1.jsonl'])==1
    assert len(rows['cases_v1.jsonl'])==int(q1 is not None)


@pytest.mark.parametrize('result,q3,q1',[
    ('找得到','PARSED','NO_MATCH'),('找不到','PARSED','READY'),('超出時間','PARSED','PARTIAL'),
    ('反問','PARSED',None),('不支援','NEEDS_CLARIFICATION',None),
])
def test_d80_original_value_contradiction_never_leaks_partial_output(tmp_path,result,q3,q1):
    p,pin,a=d80_return(tmp_path,result,q3_status=q3,q1_status=q1)
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='CSV_ANNOTATION_STATUS_MISMATCH'


@pytest.mark.parametrize('notes',['','說明=SYNTHETIC｜關鍵字=只測解析','關鍵字=只測解析x',
                                  '關鍵字=只測解析|說明=SYNTHETIC',' 關鍵字=只測解析'])
def test_d80_blank_without_exact_prefix_is_invalid(tmp_path,notes):
    p,pin,a=d80_return(tmp_path,'',q3_status='PARSED')
    edit_csv(p/TEXT_FILE,TEXT_COLUMNS,lambda row:row.update({TEXT_COLUMNS[-1]:notes}))
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='TEXT_FIELDS_MISSING_OR_INVALID'


def test_d80_keyword_at_end_of_notes_is_accepted(tmp_path):
    p,pin,a=d80_return(tmp_path,'',keyword='只測解析',q3_status='PARSED')
    edit_csv(p/TEXT_FILE,TEXT_COLUMNS,lambda row:row.update({TEXT_COLUMNS[-1]:'關鍵字=只測解析'}))
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['invalid_rows.jsonl']==[] and len(rows['queries_v1.jsonl'])==1


def test_d80_keyword_does_not_create_a_missing_human_annotation(tmp_path):
    p,pin,_=d80_return(tmp_path,'',keyword='只測解析',q3_status='PARSED')
    _,rows=run_d80(tmp_path,p,pin,None)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='PRECISE_HUMAN_ANNOTATION_REQUIRED'


@pytest.mark.parametrize('bad',['missing','missing_request','missing_query','mismatch','uppercase','short','number','array'])
def test_d80_invalid_query_binding_rejects_whole_row(tmp_path,bad):
    p,pin,a=d80_return(tmp_path,'找得到',q3_status='PARSED',q1_status='READY')
    row=json.loads(a.read_text());binding=row['q1']['query_binding']
    if bad=='missing':row['q1'].pop('query_binding')
    elif bad=='missing_request':binding.pop('request_sha256')
    elif bad=='missing_query':binding.pop('query_sha256')
    elif bad=='mismatch':binding['request_sha256']='0'*64
    elif bad=='uppercase':binding['query_sha256']='A'*64
    elif bad=='short':binding['query_sha256']='a'*63
    elif bad=='number':binding['query_sha256']=7
    else:row['q1']['query_binding']=[]
    a.write_text(json.dumps(row)+'\n')
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='QUERY_BINDING_INVALID'


def test_d80_supplied_binding_is_preserved_and_only_origin_is_excluded(tmp_path):
    p,pin,a=d80_return(tmp_path,'找得到',q3_status='PARSED',q1_status='READY')
    row=json.loads(a.read_text());binding=row['q1']['query_binding']
    binding['parse_receipt_sha256']='d'*64
    row['q1']['request']['origin']='CHANGED_EXTERNAL_ORIGIN'
    a.write_text(json.dumps(row)+'\n')
    report,rows=run_d80(tmp_path,p,pin,a)
    assert rows['invalid_rows.jsonl']==[]
    assert rows['cases_v1.jsonl'][0]['query_binding']==binding
    assert rows['cases_v1.jsonl'][0]['request']==row['q1']['request']
    assert binding['query_sha256']=='f'*64
    assert binding['query_sha256']!=sha(canonical(row['q1']['request']))
    assert report['query_binding_source']=='EVALUATION_OWNER_PER_D80'


@pytest.mark.parametrize('field',['session_id','cursor'])
def test_d80_binding_covers_session_and_cursor_fields(tmp_path,field):
    p,pin,a=d80_return(tmp_path,'找得到',q3_status='PARSED',q1_status='READY')
    row=json.loads(a.read_text());row['q1']['request'][field]='CHANGED'
    a.write_text(json.dumps(row)+'\n')
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='QUERY_BINDING_INVALID'


def test_d80_malformed_secondary_annotation_rejects_other_valid_output(tmp_path):
    p,pin,a=d80_return(tmp_path,'找得到',q3_status='PARSED',q1_status='READY')
    row=json.loads(a.read_text());row['q3']['expected_llm_output'].pop('intent')
    a.write_text(json.dumps(row)+'\n')
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='PRECISE_HUMAN_ANNOTATION_INVALID'


def test_d80_truncated_csv_row_is_invalid_without_keyword_parser_crash(tmp_path):
    p,pin,a=d80_return(tmp_path,'',keyword='只測解析',q3_status='PARSED')
    raw=(p/TEXT_FILE).read_text(encoding='utf-8-sig')
    records=list(csv.reader(io.StringIO(raw)))
    records[1]=records[1][:-1]
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerows(records);(p/TEXT_FILE).write_text(stream.getvalue(),encoding='utf-8-sig')
    _,rows=run_d80(tmp_path,p,pin,a)
    assert rows['queries_v1.jsonl']==rows['cases_v1.jsonl']==[]
    assert rows['invalid_rows.jsonl'][0]['reason']=='TEXT_FIELDS_MISSING_OR_INVALID'
