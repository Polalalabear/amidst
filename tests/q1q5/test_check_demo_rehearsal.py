"""評分端；與推論隔離。SYNTHETIC format tests, never #346 human acceptance."""
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
FIX=ROOT/'tests/fixtures/demo_rehearsal/SYNTHETIC'
sys.path.insert(0,str(ROOT/'scripts'))


def checks():
    if not (ROOT/'scripts/demo_record_checks.py').is_file():
        if os.environ.get('AMIDST_REQUIRE_IMPL')=='1':pytest.fail('DEMO_CHECKER_IMPLEMENTATION_MISSING')
        return pytest.importorskip('demo_record_checks')
    module=importlib.import_module('demo_record_checks')
    assert Path(module.__file__).resolve()==ROOT/'scripts/demo_record_checks.py'
    return module


def raw(name):return (FIX/name).read_bytes()
def record():return json.loads(raw('positive.SYNTHETIC.json'))
def encoded(doc):return json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()


def test_fixture_scope_and_independent_output_hash():
    module=checks(); doc=json.loads(raw('checklist.SYNTHETIC.json'))
    assert [row['id'] for row in doc['items']]==['B-01','B-02','C-01','C-02','D-01','D-02']
    assert record()['items'][0]['evidence'][0]['sha256']==module.sha(raw('output.SYNTHETIC.txt'))
    for path in FIX.iterdir():
        assert 'SYNTHETIC' in path.name or path.name=='README.md' and path.read_text().startswith('# SYNTHETIC')
        text=path.read_text();assert not any(x in text for x in ('/Users/','/private/','.blend'))


def test_positive_record_defaults_unreviewed_without_changing_input():
    module=checks(); source=raw('positive.SYNTHETIC.json'); before=bytes(source)
    report=module.check_record(source,raw('checklist.SYNTHETIC.json'))
    assert report['validation']=='VALID_RECORD_FORMAT' and report['result_counts']=={'PASS':6,'FAIL':0,'NOT_RUN':0}
    assert set(report['claude_review_status_reported'].values())=={'NOT_REVIEWED'}
    assert set(report['fallback_claude_review_status_reported'].values())=={'NOT_REVIEWED'}
    assert report['evidence_hashes']=='REPORTED_ONLY_NOT_READ_OR_VERIFIED'
    assert report['human_acceptance_verified'] is report['claude_review_verified'] is False
    assert source==before and 'claude_review_status' not in json.loads(source)['items'][0]


@pytest.mark.parametrize('name,message',[
    ('missing-item','exactly cover'),('pass-without-evidence','PASS requires'),('fallback-not-rehearsed','not NOT_RUN')])
def test_negative_record_fixtures(name,message):
    module=checks()
    with pytest.raises(module.CheckError,match=message):
        module.check_record(raw(name+'.SYNTHETIC.json'),raw('checklist.SYNTHETIC.json'))


@pytest.mark.parametrize('mutation', ['unknown-id','duplicate-id','wrong-pin','bad-result','bad-review','bad-sha','extra-field','duplicate-fallback','missing-fallback'])
def test_closed_schema_and_binding_failures(mutation):
    module=checks(); doc=record()
    if mutation=='unknown-id':doc['items'][0]['id']='B-99'
    if mutation=='duplicate-id':doc['items'][0]['id']=doc['items'][1]['id']
    if mutation=='wrong-pin':doc['checklist_sha256']='0'*64
    if mutation=='bad-result':doc['items'][0]['result']='ACCEPTED'
    if mutation=='bad-review':doc['items'][0]['claude_review_status']='APPROVED'
    if mutation=='bad-sha':doc['items'][0]['evidence'][0]['sha256']='claimed hash'
    if mutation=='extra-field':doc['user_accepted']=True
    if mutation=='duplicate-fallback':doc['fallback'][2]['id']='a'
    if mutation=='missing-fallback':doc['fallback'].pop()
    with pytest.raises(module.CheckError):module.check_record(encoded(doc),raw('checklist.SYNTHETIC.json'))


def test_fail_and_not_run_are_preserved_as_results_not_rewritten_to_pass():
    module=checks();doc=record()
    doc['items'][0].update(result='FAIL',evidence=[],claude_review_status='REVIEWED')
    doc['items'][1].update(result='NOT_RUN',evidence=[])
    doc['fallback'][0].update(result='FAIL',evidence=[],note='SYNTHETIC exercise attempted and failed')
    report=module.check_record(encoded(doc),raw('checklist.SYNTHETIC.json'))
    assert report['result_counts']=={'PASS':4,'FAIL':1,'NOT_RUN':1}
    assert report['fallback_results_reported']['a']=='FAIL'
    assert report['claude_review_status_reported']['B-01']=='REVIEWED' and not report['claude_review_verified']


def test_script_positive_and_short_script_coverage_is_explicit():
    module=checks(); report=module.check_script(raw('demo-script.SYNTHETIC.md'),raw('checklist.SYNTHETIC.json'))
    assert len(report['step_ids'])==6 and report['uncovered_checklist_ids']==[]
    assert report['claude_review_status']=='NOT_REVIEWED' and not report['human_acceptance_verified']
    short=b'## B-01\n'+ '操作：開頁。\n預期：合成資料。\nfallback：重播。\n'.encode()
    assert module.check_script(short,raw('checklist.SYNTHETIC.json'))['uncovered_checklist_ids']==['B-02','C-01','C-02','D-01','D-02']


@pytest.mark.parametrize('mutation',['unknown-id','duplicate-id','missing-operation','missing-expected','missing-fallback','empty-fallback','no-steps','duplicate-column'])
def test_script_rejects_missing_or_ambiguous_steps(mutation):
    module=checks();text=raw('demo-script.SYNTHETIC.md').decode()
    if mutation=='unknown-id':text=text.replace('## B-01','## B-99',1)
    if mutation=='duplicate-id':text=text.replace('## B-02','## B-01',1)
    if mutation.startswith('missing-'):
        field={'missing-operation':'操作','missing-expected':'預期','missing-fallback':'fallback'}[mutation]
        text='\n'.join(line for line in text.splitlines() if not line.startswith(field+'：'))
    if mutation=='empty-fallback':text=text.replace('fallback：使用既有合成 replay。','fallback：',1)
    if mutation=='no-steps':text='# SYNTHETIC empty'
    if mutation=='duplicate-column':text+='fallback：duplicate\n'
    with pytest.raises(module.CheckError):module.check_script(text.encode(),raw('checklist.SYNTHETIC.json'))


@pytest.mark.parametrize('bait',['t_X = 1.0','`t_N_us`: 2400000','GT = 1','gt_actor_id: 1',
    'decision_window_us: [1, 2]','評分窗 [1,2)','ｔ＿Ｘ＝１','visibility: 1'])
def test_private_value_baits_are_rejected_in_records_and_scripts(bait):
    module=checks();doc=record();doc['items'][0]['note']='SYNTHETIC bait '+bait
    with pytest.raises(module.CheckError):module.check_record(encoded(doc),raw('checklist.SYNTHETIC.json'))
    with pytest.raises(module.CheckError):module.check_script(raw('demo-script.SYNTHETIC.md')+bait.encode(),raw('checklist.SYNTHETIC.json'))


def test_gt_isolation_language_without_values_is_allowed():
    module=checks();doc=record();doc['items'][0]['note']='檢查 GT 隔離，未讀取任何 GT；評分窗不顯示。'
    assert module.check_record(encoded(doc),raw('checklist.SYNTHETIC.json'))['validation']=='VALID_RECORD_FORMAT'


@pytest.mark.parametrize('payload',[b'{"a":1,"a":2}',b'{"a":NaN}',b'not json'])
def test_duplicate_and_malformed_json_fail_closed(payload):
    module=checks()
    with pytest.raises(module.CheckError):module.decode(payload)


def test_checklist_duplicates_and_schema_drift_are_rejected():
    module=checks();doc=json.loads(raw('checklist.SYNTHETIC.json'));doc['items'].append(deepcopy(doc['items'][0]))
    with pytest.raises(module.CheckError,match='Duplicate checklist'):module.checklist(encoded(doc))
    with pytest.raises(module.CheckError,match='Unsupported local schema keyword'):
        module.schema_check('text',{'type':'string','format':'unimplemented'})


def test_symlinks_and_parent_aliases_are_refused(tmp_path):
    module=checks();target=tmp_path/'one.json';target.write_text('{}')
    alias=tmp_path/'alias.json';alias.symlink_to(target)
    with pytest.raises(module.CheckError):module.read(alias)
    with pytest.raises(module.CheckError):module.read(tmp_path/'unused'/'..'/'one.json')


@pytest.mark.parametrize('kind,name,expected', [('record','positive.SYNTHETIC.json',0),
    ('record','missing-item.SYNTHETIC.json',2),('record','pass-without-evidence.SYNTHETIC.json',2),
    ('record','fallback-not-rehearsed.SYNTHETIC.json',2),('script','demo-script.SYNTHETIC.md',0)])
def test_actual_cli_positive_and_negative(kind,name,expected):
    checks(); tool='check_demo_rehearsal.py' if kind=='record' else 'check_demo_script.py'
    result=subprocess.run([sys.executable,str(ROOT/'scripts'/tool),'--'+kind,str(FIX/name),
        '--checklist',str(FIX/'checklist.SYNTHETIC.json')],capture_output=True,text=True,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    assert result.returncode==expected,result.stderr
    if expected==0:assert json.loads(result.stdout)['human_acceptance_verified'] is False
    else:assert result.stdout=='' and result.stderr
