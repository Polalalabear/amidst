"""Portable pack keeps source data fixed and all reviewer choices blank."""

import pytest

from amidst.q1q5.portable_pack import CRITERIA, MODULES, return_form, safe_relative


@pytest.mark.parametrize('value',[None,'','/Users/example/file','../file','a/../../file','a\\file'])
def test_portable_refs_never_require_the_builders_home(value):
    with pytest.raises(ValueError):safe_relative(value)


def test_portable_refs_keep_relative_space_and_unicode():
    assert str(safe_relative('data/工程 scene/rgb.json'))=='data/工程 scene/rgb.json'


def test_return_form_has_eight_blank_results_and_human_filename():
    form=return_form()
    assert len(CRITERIA)==8 and form.count('data-code=')==8
    assert form.count('<option value="">請選擇</option>')==8
    assert '測試回報_' in form and 'text/csv;charset=utf-8' in form and '不確定' in form
    assert '<option selected>T' not in form


def test_bundle_does_not_ship_detector_or_producer_modules():
    assert 'detection_index' not in MODULES and 'dynamic_rgb_producer' not in MODULES
    assert 'p1_workbench' in MODULES and 'q5_controller' in MODULES


@pytest.mark.parametrize('private', ['/' + name + '/someone/file' for name in ['Users','home','private','tmp']])
def test_payload_scanner_rejects_private_locators_in_nested_recording(tmp_path,private):
    from amidst.q1q5.portable_pack import scan_private_locators
    (tmp_path/'recording.json').write_text('{"ref":"'+private+'"}',encoding='utf-8')
    with pytest.raises(ValueError,match='PRIVATE_LOCATOR_IN_PAYLOAD'):
        scan_private_locators(tmp_path)


def test_return_templates_are_pinned_and_new_return_files_remain_allowed(tmp_path):
    from amidst.q1q5.p1_workbench import verify_bundle
    from amidst.q1q5.portable_pack import write_manifest
    returns=tmp_path/'RETURN';returns.mkdir()
    (returns/'index.html').write_text('form',encoding='utf-8')
    (returns/'blank.csv').write_text('blank',encoding='utf-8')
    manifest,pin=write_manifest(tmp_path,'a'*40)
    assert {'RETURN/index.html','RETURN/blank.csv'}<=manifest['files'].keys()
    (returns/'human-return.csv').write_text('human',encoding='utf-8')
    verify_bundle(tmp_path,pin)
    (returns/'index.html').write_text('tampered',encoding='utf-8')
    with pytest.raises(ValueError,match='BUNDLE_SIZE_MISMATCH'):
        verify_bundle(tmp_path,pin)


def test_json_bytes_are_sorted_and_utf8_independent_of_locale(tmp_path):
    from amidst.q1q5.portable_pack import scan_private_locators, write_json
    a,b=tmp_path/'a.json',tmp_path/'b.json'
    write_json(a,{'z':'中文','a':1});write_json(b,{'a':1,'z':'中文'})
    assert a.read_bytes()==b.read_bytes() and '中文'.encode() in a.read_bytes()
    scan_private_locators(tmp_path)


def test_real_shipped_modules_are_source_code_but_data_still_scanned(tmp_path):
    from pathlib import Path
    from amidst.q1q5.portable_pack import scan_private_locators
    source = Path(__file__).resolve().parents[2] / 'src/amidst/q1q5'
    target = tmp_path / 'app/src/amidst/q1q5'
    target.mkdir(parents=True)
    for module in MODULES:
        (target / (module + '.py')).write_bytes((source / (module + '.py')).read_bytes())
    scan_private_locators(tmp_path)
    payload = tmp_path / 'data/recordings/case.json'
    payload.parent.mkdir(parents=True)
    payload.write_text('{"ref":"' + '/Users/' + 'private-user/input.json"}', encoding='utf-8')
    with pytest.raises(ValueError, match='PRIVATE_LOCATOR_IN_PAYLOAD: data/recordings/case.json'):
        scan_private_locators(tmp_path)


@pytest.mark.parametrize('locator', ['/var/hidden/a.json', '/Volumes/Disk/a.json', r'C:\Users\someone\a.json', 'D:/data/a.json'])
def test_payload_scanner_covers_other_platform_locators(tmp_path, locator):
    from amidst.q1q5.portable_pack import scan_private_locators
    (tmp_path / 'SOURCE.json').write_text(locator, encoding='utf-8')
    with pytest.raises(ValueError, match='PRIVATE_LOCATOR_IN_PAYLOAD'):
        scan_private_locators(tmp_path)
