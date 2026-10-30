"""評分端；與推論隔離。CQ-39-T synthetic return integrity and freeze-before-script."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
FIXTURES = ROOT/'tests/fixtures/team_eval_return/SYNTHETIC'
KINDS = ['complete','wrong_manifest','tampered','missing','incomplete','environment_drift']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


class FreezeGate:
    """Test observer only: native code must freeze first; this creates no receipt."""
    def __init__(self,root,script,expected):
        self.root,self.script,self.expected = root.resolve(),script.resolve(),expected
        self.frozen = False
        self.active = True
        self.script_reads = 0
        self.premature = 0
        sys.addaudithook(self.audit)

    def audit(self,event,args):
        if self.active and event == 'open' and isinstance(args[0],(str,bytes)):
            path = Path(os.fsdecode(args[0])).absolute()
            if path.resolve() == self.script:
                if not self.frozen:
                    self.premature += 1
                    raise AssertionError('CQ39_SCRIPT_READ_BEFORE_VERIFIED_FREEZE')
                self.script_reads += 1

    def frozen_receipt(self,ref):
        receipt = Path(ref['receipt_path']).absolute()
        assert receipt.resolve() == receipt and receipt.is_relative_to(self.root/'freeze-output')
        assert sha(receipt.read_bytes()) == ref['receipt_sha256']
        assert set(ref['files']) == set(self.expected)
        for name,artifact in ref['files'].items():
            path = Path(artifact['path']).absolute()
            assert path.resolve() == path and path.is_relative_to(self.root/'freeze-output')
            assert path.read_bytes() == self.expected[name]
            assert sha(path.read_bytes()) == artifact['sha256']
        # Callback is allowed only after real files and the native receipt exist with correct bytes.
        self.frozen = True


def invoke(operation,**kwargs):
    name = os.environ.get('AMIDST_TEAM_RETURN_MODULE','amidst.evaluation.team_eval_return_scoring')
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ39_IMPLEMENTATION_MISSING')
        pytest.importorskip(name,reason='CQ39_IMPLEMENTATION_MISSING')
    module = importlib.import_module(name)
    selected = os.environ.get('AMIDST_TEAM_RETURN_DRIVER')
    if not selected:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ39_TEST_DRIVER_UNBOUND')
        pytest.skip('CQ39_TEST_DRIVER_UNBOUND')
    driver = importlib.import_module(selected)
    path = Path(module.__file__).resolve(); calls = []
    previous = sys.getprofile()
    def trace(frame,event,arg):
        if event == 'call' and Path(frame.f_code.co_filename).resolve() == path:
            calls.append(frame.f_code.co_name)
    try:
        sys.setprofile(trace)
        result = driver.exercise(operation,implementation=module,**kwargs)
    except (pytest.skip.Exception,pytest.xfail.Exception):
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ39_REQUIRED_DRIVER_BINDING_MISSING')
        raise
    finally:
        sys.setprofile(previous)
    assert calls and result['implementation_file_sha256'] == sha(path.read_bytes())
    assert result['human_approval_verified'] is False
    return result


def prepare(tmp_path,kind):
    root = tmp_path/'SYNTHETIC';shutil.copytree(FIXTURES/kind,root)
    case = load(root/'case.SYNTHETIC.json');returned = load(root/case['return_path'])
    sources = [case['return_path'],*returned['return_files'].values()]
    expected = {name:(root/name).read_bytes() for name in sources if (root/name).is_file()}
    original = {name:(root/name).read_bytes() for name in case['original_files'].values()}
    gate = FreezeGate(root,root/case['script_path'],expected)
    return root,case,gate,original


def test_six_fixture_integrity_distinguishes_tamper_from_drift():
    assert {p.name for p in FIXTURES.iterdir() if p.is_dir()} == set(KINDS)
    for kind in KINDS:
        root = FIXTURES/kind;case = load(root/'case.SYNTHETIC.json');ret = load(root/case['return_path'])
        assert case['fixture_role'] == 'SYNTHETIC_ONLY'
        assert (ret['pack_manifest_sha256'] == sha((root/case['manifest_path']).read_bytes())) == (kind != 'wrong_manifest')
        for key,name in ret['return_files'].items():
            path = root/name
            if kind == 'missing' and key == 'complex':
                assert not path.exists();continue
            equal = sha(path.read_bytes()) == ret['output_sha256'][key]
            assert equal == (kind != 'tampered' or key != 'complex')
        if kind == 'environment_drift':
            assert (root/'returned/complex.json').read_bytes() != (root/'original/complex.json').read_bytes()
        if kind == 'incomplete':
            assert '_INCOMPLETE' in case['return_path']


def test_script_read_observer_fails_before_freeze(tmp_path):
    root,case,gate,_ = prepare(tmp_path,'complete')
    try:
        with pytest.raises(AssertionError,match='CQ39_SCRIPT_READ_BEFORE_VERIFIED_FREEZE'):
            (root/case['script_path']).read_bytes()
        assert gate.premature == 1 and gate.script_reads == 0
    finally:
        gate.active = False


@pytest.mark.parametrize('kind',KINDS)
def test_native_return_verification_freeze_and_scoring(tmp_path,kind):
    root,case,gate,original = prepare(tmp_path,kind)
    try:
        result = invoke('receive_and_score',root=root,case=case,freeze_output=root/'freeze-output',
                        freeze_verified=gate.frozen_receipt,test_profile='CQ39_TEST_RETURN_V1')
        assert gate.premature == 0
        assert all((root/name).read_bytes() == raw for name,raw in original.items())
        if kind in {'wrong_manifest','tampered','missing'}:
            assert result['status'] == 'INVALID' and result.get('score') is None
            assert gate.script_reads == 0
            return
        assert gate.frozen
        if kind == 'incomplete':
            assert result['accepted'] is True and result['included_in_formal_denominator'] is False
            return
        assert gate.script_reads > 0
        direct = invoke('score_direct_frozen',root=root,case=case,test_profile='CQ39_TEST_RETURN_V1')
        assert isinstance(direct['score'],dict) and direct['score']
        if kind == 'complete':
            assert result['status'] == 'SCORED' and result['score'] == direct['score']
        else:
            assert result['status'] == 'ENVIRONMENT_DRIFT'
            assert result['frozen_score'] == direct['score']
            assert isinstance(result['returned_score'],dict) and result['returned_score']
            assert result['frozen_output_sha256'] != result['returned_output_sha256']
        assert all((root/name).read_bytes() == raw for name,raw in original.items())
    finally:
        gate.active = False


def test_native_refuses_score_without_freeze_before_opening_script(tmp_path):
    root,case,gate,_ = prepare(tmp_path,'complete')
    try:
        result = invoke('score_without_freeze',root=root,case=case,test_profile='CQ39_TEST_RETURN_V1')
        assert result['status'] == 'INVALID' and result['reason_category'] == 'RETURN_NOT_FROZEN'
        assert gate.premature == gate.script_reads == 0 and gate.frozen is False
    finally:
        gate.active = False
