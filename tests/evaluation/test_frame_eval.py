from amidst.evaluation import frame_eval as fe

BODY = [100, 100, 140, 220]


def det(i, box, score=0.9, cls='person', verdict='STRONG'):
    return {'id': i, 'box': box, 'score': score, 'cls': cls, 'verdict_red': verdict, 'colors': ['red'] if verdict else []}


def test_labels_and_strata():
    lab = fe.frame_labels([det('D1', [105, 110, 135, 215], cls='sports ball', score=0.4)], BODY, 960, 540, red_px=200, red_share=0.08)
    assert lab['present'] and not lab['person_on_target'] and lab['n_on_target'] == 1
    assert 'nonperson_class' in fe.strata_of(lab, (50, 150))
    hidden = fe.frame_labels([], BODY, 960, 540, red_px=0, red_share=0.0)     # in frustum, no pixels: behind a wall
    assert not hidden['present'] and fe.strata_of(hidden, (50, 150)) == ['neg_occluded']
    out = fe.frame_labels([], [2000, 100, 2040, 220], 960, 540)
    assert fe.strata_of(out, (50, 150)) == ['neg_absent']


def test_rule_and_scoring():
    on = det('D1', [105, 110, 135, 215])
    other = det('D2', [500, 110, 530, 215], score=0.95)
    lab = fe.frame_labels([on, other], BODY, 960, 540, red_px=300, red_share=0.1)
    ans = fe.rule_answer([on, other], 'red')
    assert ans['present'] and ans['det'] == 'D2'          # best (verdict, -score) is the other person -> wrong box
    assert fe.score_frame(ans, {'D1': on, 'D2': other}, lab, BODY)['out'] == 'FP_wrong_box'
    assert fe.score_frame({'present': True, 'det': 'D1', 'box': None}, {'D1': on}, lab, BODY)['out'] == 'TP'
    assert fe.score_frame({'present': True, 'det': None, 'box': [101, 101, 139, 219]}, {}, lab, BODY)['src'] == 'OWN'
    assert fe.score_frame({'present': False, 'det': None, 'box': None}, {}, lab, BODY)['out'] == 'FN'
    absent = fe.frame_labels([], BODY, 960, 540, red_px=0)
    assert fe.score_frame({'present': True, 'det': 'D1', 'box': None}, {'D1': on}, absent, None)['out'] == 'FP_absent'
    assert fe.score_frame({'present': False, 'det': None, 'box': None}, {}, absent, None)['out'] == 'TN'


def test_parse_and_prf():
    assert fe.parse_answer('x', set(), True)[1] == 'NOT_JSON'
    assert fe.parse_answer('{"present": true, "detection_id": "D9"}', {'D1'}, True)[1] == 'BAD_DETECTION_ID'
    a, e = fe.parse_answer('{"present": true, "detection_id": null, "box_xyxy": [1,2,30,40]}', set(), False)
    assert a is None and e == 'NO_TARGET_REF'                     # pick-only arm ignores own boxes
    m = fe.prf(['TP', 'TP', 'FP_wrong_box', 'FN', 'TN'])
    assert round(m['precision'], 3) == 0.667 and round(m['recall'], 3) == 0.5
