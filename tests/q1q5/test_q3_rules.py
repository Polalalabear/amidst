"""SYNTHETIC grammar checks, not an authored evaluation question bank."""
import pytest
from amidst.q1q5.q3_rules import parse_rule

ALIASES=dict(class_aliases={'人':'person','person':'person','車':'car','汽車':'car'},color_aliases={'紅':'red','紅色':'red','藍':'blue'},camera_aliases={'CAM_A':'A'},region_aliases={'REG_A':'R'})


def rule(text):return parse_rule(text,**ALIASES)


def test_literal_terms_and_period_inheritance_are_not_rewritten():
    d=rule('跟著紅衣人下午1點到1:30').output
    assert d['intent']=='FIND_PERSON' and d['class_term']=='人' and d['color_term']=='紅'
    assert d['time_literal']=={'start':'下午1點','end':'1:30','date':None}
    assert not d['needs_clarification']


def test_nested_aliases_map_once_and_camera_region_are_literal():
    d=rule('汽車 CAM_A REG_A 13:00到13:10').output
    assert d['class_term']=='汽車' and not d['needs_clarification']
    assert d['camera_terms']==['CAM_A'] and d['region_terms']==['REG_A']


@pytest.mark.parametrize('text',['找他','紅衣人','人13:00','人13:00到13:10和13:20','人車13:00到13:10','紅藍人13:00到13:10'])
def test_missing_or_ambiguous_constraints_require_clarification(text):
    assert rule(text).output['needs_clarification']


def test_iso_offsets_are_one_time_token_each():
    d=rule('車2026-11-01T13:00:00+08:00到2026-11-01T13:01:00+08:00').output
    assert d['time_literal']['end']=='2026-11-01T13:01:00+08:00' and not d['needs_clarification']


def test_unknown_class_and_unknown_modifier_are_preserved():
    assert rule('樹13:00到13:10').output['class_term']=='樹'
    assert rule('戴眼鏡的人13:00到13:10').unsupported_condition
    assert rule('拿著物品的人13:00到13:10').unparsed


def test_ascii_alias_is_not_substring_of_another_word():
    assert rule('cart13:00到13:10').output['class_term']=='cart'


@pytest.mark.parametrize('text',['',' ',None])
def test_empty_input_refused(text):
    with pytest.raises(ValueError):rule(text)
