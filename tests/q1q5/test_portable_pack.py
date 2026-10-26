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
