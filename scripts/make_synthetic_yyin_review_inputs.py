#!/usr/bin/env python3
"""Make tiny explicit SYNTHETIC s1 inputs; no source image is copied."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.yyin_main_pack import canonical, sha
from amidst.q1q5.yyin_review_pack import ANSWERS, CAMERAS, FILES


def make(output):
    output = Path(output).absolute()
    if output.resolve() != output or output.exists() or 'SYNTHETIC' not in str(output):
        raise ValueError('New canonical SYNTHETIC directory required')
    output.mkdir()
    doc = {'fixture_role': 'SYNTHETIC', 'gt_read': False, 'rendered': False,
           'source_blend_read': False, 'events_read': False, 'files': {}, 'questions': []}
    for i, name in enumerate(FILES):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="180" viewBox="0 0 640 180">'
               '<rect width="640" height="180" fill="#eeeeee"/><text x="20" y="30">SYNTHETIC ONLY</text>'
               '<text x="20" y="100">A</text><text x="220" y="100">B</text><text x="420" y="100">C</text></svg>').encode()
        (output / name).write_bytes(svg)
        doc['files'][name] = sha(svg)
        doc['questions'].append({'file': name, 'camera_id': CAMERAS[i], 'allowed_answers': list(ANSWERS)})
    receipt = canonical(doc)
    (output / 'RECEIPT.json').write_bytes(receipt)
    path = output / 'inputs.json'
    path.write_bytes(canonical({'path': str(output), 'receipt_sha256': sha(receipt)}))
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(make(parser.parse_args().output))
