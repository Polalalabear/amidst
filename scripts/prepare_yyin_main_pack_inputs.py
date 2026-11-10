"""Write explicit LOCAL s2 source locators after checking the selected pins."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.yyin_main_pack import PINS, SOURCE_MANIFEST, regular, require, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pack', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = args.source_pack.resolve()
    require(sha(regular(source / 'MANIFEST.json').read_bytes()) == SOURCE_MANIFEST,
            'SOURCE_MANIFEST_PIN_MISMATCH')
    paths = {'clock': 'configs/q1q5/clocks/r004_a4_v1.json',
             'run': 'configs/q1q5/runs/r004_a4_v1.json',
             'catalog_receipt': 'docs/history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json',
             'object_list': 'docs/evaluation/R004_STATIC_QUESTIONABLE_OBJECTS_20261029.json'}
    config = {'source_pack': {'path': str(source), 'manifest_sha256': SOURCE_MANIFEST}}
    for name, ref in paths.items():
        path = regular(repo / ref)
        require(sha(path.read_bytes()) == PINS[name], 'INPUT_PIN_MISMATCH: ' + name)
        config[name] = {'path': str(path), 'sha256': PINS[name]}
    with args.output.open('xb') as stream:
        stream.write(json.dumps(config, sort_keys=True, separators=(',', ':')).encode() + b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
