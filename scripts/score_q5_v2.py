"""Score pinned outputs without selecting unresolved v2 decisions or authority."""
import argparse
from pathlib import Path

from amidst.evaluation import q5_switch_eval as v1
from amidst.evaluation import q5_switch_eval_v2 as v2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('response', 'decisions', 'script', 'parameters', 'plan', 'decisions-config'):
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        paths = {name: Path(getattr(args, name)).absolute() for name in ('response', 'decisions', 'script', 'parameters', 'plan')}
        pins = {name: getattr(args, name + '_sha256') for name in paths}
        choices = Path(args.decisions_config)
        v1.require(choices.resolve() == choices.absolute() and choices.is_file() and not choices.is_symlink(), 'Canonical decision config required')
        raw = choices.read_bytes(); pins['decisions_config'] = args.decisions_config_sha256
        v1.require(v1.sha(raw) == pins['decisions_config'], 'Decision config file hash mismatch')
        # No CLI switch can promote synthetic controls to formal prefix/G4 evidence.
        report = v2.score_files(paths, pins, decisions_raw=raw)
        with Path(args.output).open('xb') as output:
            output.write(v1.canonical(report) + b'\n')
    except (v1.EvaluationError, OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
