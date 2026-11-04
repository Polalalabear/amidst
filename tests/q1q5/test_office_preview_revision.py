"""V2 authorization/source boundaries; never render during pytest."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import revise_office_static_preview as v


def test_v2_help_imports_without_bpy_or_writing(tmp_path):
    r=subprocess.run([sys.executable,'-S',str(Path(v.__file__)),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert r.returncode==0 and '--authorization-ref' in r.stdout
    assert not list(tmp_path.iterdir())


def test_blender_style_script_loader_without_scripts_on_sys_path(tmp_path):
    code='import runpy; runpy.run_path('+repr(str(Path(v.__file__)))+', run_name="producer_import_probe")'
    r=subprocess.run([sys.executable,'-S','-c',code],cwd=tmp_path,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert not list(tmp_path.iterdir())


def test_v2_authorization_precedes_source_access(tmp_path):
    with pytest.raises(ValueError,match='EXPLICIT_AUTHORIZATION_REQUIRED'):
        v.main(['--execute','--correction',str(tmp_path/'missing.json')])
    assert not list(tmp_path.iterdir())


def test_correction_is_the_exact_approved_scope(tmp_path):
    d=v.correction()
    assert d['overrides']['view_exposure_ev']==-4
    assert d['overrides']['human_overhead_orthographic_scale_m']==26
    assert d['scope']['animation'] is False and d['scope']['video'] is False
    p=tmp_path/'tampered.json';p.write_bytes(v.CORRECTION.read_bytes()+b' ')
    with pytest.raises(ValueError,match='CORRECTION_PIN'):v.correction(p)


def test_source_symlink_is_refused_before_read(tmp_path,monkeypatch):
    root=tmp_path/'v1';root.mkdir();outside=tmp_path/'outside';outside.write_text('not-read')
    (root/'build_receipt.json').symlink_to(outside)
    monkeypatch.setattr(v,'SOURCE',root)
    with pytest.raises(ValueError,match='SYMLINK_FORBIDDEN'):v.source_inputs()


def test_unpinned_source_receipt_does_not_reach_blender(tmp_path,monkeypatch):
    root=tmp_path/'v1';root.mkdir();(root/'build_receipt.json').write_text('{}')
    monkeypatch.setattr(v,'SOURCE',root)
    with pytest.raises(ValueError,match='V1_RECEIPT_PIN'):v.source_inputs()
