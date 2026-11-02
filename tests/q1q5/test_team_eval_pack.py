"""CQ-14-T: isolated offline replay of SYNTHETIC frozen bytes; no evaluation truth."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
FIXTURES = ROOT / 'tests/fixtures/team_eval_pack/SYNTHETIC'
PROFILE = 'CQ14_TEST_RETURN_V1'
BOOTSTRAP = '''import runpy,sys
assert sys.flags.isolated == 1

def audit(event,args):
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.posix_spawn','os.spawn'}:
        raise RuntimeError('CQ14_NETWORK_OR_CHILD_PROCESS_BLOCKED')
sys.addaudithook(audit)
entry=sys.argv[1]
sys.argv=sys.argv[1:]
runpy.run_path(entry,run_name='__main__')
'''


def missing(reason):
    if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
        pytest.fail(reason)
    pytest.skip(reason)


def python312():
    candidate = shutil.which('python3.12')
    if candidate is None and sys.version_info[:2] == (3, 12):
        candidate = sys.executable
    if candidate is None:
        missing('PYTHON_3_12_NOT_FOUND')
    result = subprocess.run([candidate, '-I', '-c', 'import sys;print(sys.version_info[:2])'], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == '(3, 12)'
    return candidate


def call(operation, **kwargs):
    name = os.environ.get('AMIDST_TEAM_EVAL_MODULE', 'amidst.q1q5.team_eval_pack')
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ14_IMPLEMENTATION_MISSING')
        pytest.importorskip(name, reason='CQ14_IMPLEMENTATION_MISSING')
    implementation = importlib.import_module(name)
    selected = os.environ.get('AMIDST_TEAM_EVAL_DRIVER')
    if not selected:
        missing('CQ14_TEST_DRIVER_UNBOUND')
    driver = importlib.import_module(selected)
    path = Path(implementation.__file__).resolve(); invoked = []
    old = sys.getprofile()
    def trace(frame,event,arg):
        if event == 'call' and Path(frame.f_code.co_filename).resolve() == path:
            invoked.append(frame.f_code.co_name)
    try:
        sys.setprofile(trace)
        result = driver.exercise(operation, implementation=implementation, **kwargs)
    except (pytest.skip.Exception, pytest.xfail.Exception):
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ14_REQUIRED_DRIVER_BINDING_MISSING')
        raise
    finally:
        sys.setprofile(old)
    assert invoked, 'Must call real implementation; no fake builder or verifier'
    assert result['implementation_file_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['human_approval_verified'] is False
    return result


def within(root, name):
    rel = Path(name)
    assert not rel.is_absolute() and '..' not in rel.parts and rel.as_posix() == name
    path = root / rel
    assert path.resolve() == path
    return path


def build(tmp_path):
    result = call('build', output=tmp_path/'SYNTHETIC-pack', inputs=FIXTURES/'inputs.SYNTHETIC.json', test_profile=PROFILE)
    root = Path(result['root']).absolute()
    assert root == (tmp_path/'SYNTHETIC-pack').absolute() and root.resolve() == root
    assert result['release_authorized'] is False
    assert hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest() == result['manifest_sha256']
    return root, result


def test_fixture_bytes_and_return_example_are_explicitly_synthetic():
    doc = json.loads((FIXTURES/'inputs.SYNTHETIC.json').read_bytes())
    assert doc['fixture_role'] == 'SYNTHETIC_ONLY'
    assert set(doc['frozen_outputs']) == {'BASELINE','COMPLEX'}
    for ref in doc['frozen_outputs'].values():
        raw = within(FIXTURES,ref['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == ref['sha256'] and b'SYNTHETIC' in raw
    example = json.loads((FIXTURES/'return.SYNTHETIC.example.json').read_bytes())
    assert example['projection'] == PROFILE and example['schema_candidate'] == 'team-eval-return.v1'
    assert set(example['output_sha256']) == {'BASELINE','COMPLEX'}


def test_python312_isolated_network_guard_itself(tmp_path):
    probe = tmp_path/'probe.py'
    probe.write_text("import socket\ntry:\n socket.socket()\nexcept RuntimeError as e:\n print(str(e))\nelse:\n raise AssertionError('network guard inactive')\n")
    run = subprocess.run([python312(), '-I', '-c', BOOTSTRAP, str(probe)], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout.strip() == 'CQ14_NETWORK_OR_CHILD_PROCESS_BLOCKED'


def test_real_pack_runs_python312_isolated_offline_and_replays_exact_bytes(tmp_path):
    interpreter = python312(); root, spec = build(tmp_path)
    scratch = tmp_path/'empty-cwd'; scratch.mkdir()
    entry = within(root,spec['entrypoint']); assert entry.is_file()
    assert isinstance(spec['entry_args'],list) and all(isinstance(v,str) for v in spec['entry_args'])
    env = {'PATH':os.environ.get('PATH',''), 'HOME':str(scratch), 'PYTHONPATH':str(ROOT/'src')}
    run = subprocess.run([interpreter, '-I', '-c', BOOTSTRAP, str(entry), *spec['entry_args']], cwd=scratch, env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    inputs = json.loads((FIXTURES/'inputs.SYNTHETIC.json').read_bytes())
    assert set(spec['replayed_files']) == {'BASELINE','COMPLEX'}
    for key,ref in inputs['frozen_outputs'].items():
        assert within(root,spec['replayed_files'][key]).read_bytes() == (FIXTURES/ref['path']).read_bytes()
    returned = within(root,spec['return_path']); assert returned.is_file()
    checked = call('validate_return',root=root,returned=returned,manifest_sha256=spec['manifest_sha256'],test_profile=PROFILE)
    assert checked['status'] == 'VALID'
    observation = checked['observations']
    assert observation['pack_manifest_sha256'] == spec['manifest_sha256']
    assert observation['environment']['python_version'].startswith('3.12.')
    assert observation['environment']['isolated'] is True and observation['environment']['platform']
    assert observation['output_sha256'] == {key:ref['sha256'] for key,ref in inputs['frozen_outputs'].items()}


@pytest.mark.parametrize('missing_field',['pack_manifest_sha256','environment','output_sha256'])
def test_return_missing_required_field_invalid(tmp_path,missing_field):
    result = call('return_missing_field',example=FIXTURES/'return.SYNTHETIC.example.json',missing_field=missing_field,output=tmp_path,test_profile=PROFILE)
    assert result['status'] == 'INVALID'


def test_proposed_return_wire_default_stays_closed(tmp_path):
    result = call('validate_unselected_return',example=FIXTURES/'return.SYNTHETIC.example.json',output=tmp_path,test_profile=None)
    assert result['status'] == 'INVALID' and result['reason_category'] == 'CONTRACT_UNSELECTED'


@pytest.mark.parametrize('mode,expected',[('complete','VALID'),('template_missing','VALID_WITH_WARNINGS'),('payload_tampered','INVALID')])
def test_real_verify_complete_template_warning_and_tamper(tmp_path,mode,expected):
    root,spec = build(tmp_path)
    if mode == 'template_missing':
        template = within(root,spec['optional_template']); assert template.is_file(); template.unlink()
    elif mode == 'payload_tampered':
        payload = within(root,spec['immutable_probe_file']); payload.write_bytes(payload.read_bytes()+b'changed')
    result = call('verify',root=root,manifest_sha256=spec['manifest_sha256'],test_profile=PROFILE)
    assert result['status'] == expected
    if mode == 'template_missing':
        assert result['warnings'] and 'TEMPLATE_MISSING' in result['reason_codes']


def test_pack_readme_launcher_and_no_private_scoring_payload(tmp_path):
    root,spec = build(tmp_path)
    readme = within(root,spec['readme']).read_text()
    assert all(word in readme for word in ['工作內容','要提交','操作'])
    assert (root/'start.command').is_file()
    forbidden = re.compile(r'\bGT\b|t_X|t_N|評分窗|renderer|visibility|depth|trajectory|\.blend|/Users/|/private/|[A-Za-z]:\\',re.I)
    for path in root.rglob('*'):
        assert not path.is_symlink()
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        assert not re.search(r'\.pt$|\.safetensors$|\.onnx$',name,re.I)
        assert not forbidden.search(name)
        # Source may include denial constants; data may not expose scoring inputs.
        if path.suffix.lower() in {'.json','.jsonl','.csv','.md','.txt','.html'}:
            assert not forbidden.search(path.read_text(encoding='utf-8-sig'))
