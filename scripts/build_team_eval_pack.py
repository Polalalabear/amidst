#!/usr/bin/env python3
"""Build a pinned offline #293 candidate. No release authorization is granted."""
import argparse
import json
from pathlib import Path

from amidst.q1q5 import team_eval_pack as pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--zip', type=Path)
    parser.add_argument('--profile', choices=[pack.SYNTHETIC, pack.BASELINE])
    parser.add_argument('--synthetic-inputs', type=Path)
    parser.add_argument('--baseline', action='append', type=Path)
    parser.add_argument('--baseline-sha256', action='append')
    parser.add_argument('--source-name', action='append')
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    try:
        pack.need(not args.receipt.exists(), 'OUTPUT_EXISTS_OR_UNSAFE')
        if args.synthetic_inputs:
            pack.need(not args.baseline, 'INPUT_INVALID')
            result = pack.build_from_inputs(args.synthetic_inputs, args.output, profile=args.profile)
        else:
            paths, pins = args.baseline or [], args.baseline_sha256 or []
            names = args.source_name or [path.name for path in paths]
            pack.need(args.profile == pack.BASELINE and len(paths) == len(pins) == len(names) and paths,
                      'CONTRACT_UNSELECTED')
            refs = [{'path': path, 'sha256': pin, 'source_name': name} for path, pin, name in zip(paths, pins, names)]
            result = pack.build_pack(args.output, {'baseline': refs}, profile=args.profile)
        receipt = {'manifest_sha256': result['manifest_sha256'], 'source_pins': result['manifest']['source_pins'],
                   'halves': result['manifest']['halves'], 'release_authorized': False}
        if args.zip:
            receipt['zip_sha256'] = pack.write_zip(args.output, args.zip)
            receipt['zip_bytes'] = args.zip.stat().st_size
        with args.receipt.open('xb') as stream:
            stream.write(pack.encode(receipt))
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'INVALID', 'reason': str(exc) if isinstance(exc, pack.PackError) else 'INPUT_INVALID'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
