"""#619: the red/blue label threshold ('weak') is a parameter; its default stays the D131 value."""
import numpy as np

from amidst.live_mode.color import CFG, judge
from amidst.live_mode.server import COLOR_WEAK_DEFAULT


def _image(red_share):
    """320x180 grey frame; a person box (100,40)-(140,120) whose top-half crop is `red_share` red."""
    img = np.full((180, 320, 3), 128, dtype=np.uint8)
    crop_h, w = 20, 40                      # top 50 % of the 40 px tall box
    n = int(round(red_share * w))
    img[40:40 + crop_h, 100:100 + n] = (192, 24, 24)
    return img, [100, 40, 140, 80]


def test_offline_default_stays_d131_and_live_default_is_0_2():
    assert CFG["weak"] == 0.3 and COLOR_WEAK_DEFAULT == 0.2
    img, box = _image(0.5)
    assert judge(img, box)["color"] == "red"


def test_share_between_weak_values_changes_only_the_label():
    img, box = _image(0.25)
    strict, loose = judge(img, box), judge(img, box, weak=0.2)
    assert strict["color"] == "none" and loose["color"] == "red"
    assert strict["red_ratio"] == loose["red_ratio"]


def test_weak_does_not_make_a_blue_person_red_or_a_grey_one_coloured():
    img = np.full((180, 320, 3), 128, dtype=np.uint8)
    box = [100, 40, 140, 80]
    assert judge(img, box, weak=0.1)["color"] == "none"
    img[40:60, 100:140] = (37, 71, 200)
    assert judge(img, box, weak=0.1)["color"] == "blue"
