"""UNFROZEN evaluation producer draft; no renderer or runtime execution."""
import argparse
from pathlib import Path

from amidst.evaluation import q5_switch_eval as v1
from amidst.evaluation.q5_script_adapter_v2 import PlanError, generate_script


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('plan', 'parameters', 'decisions-config'):
        parser.add_argument('--' + key, required=True)
        parser.add_argument('--' + key + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--formal', action='store_true', help='Always refused until U6/U7 evidence adapters are adopted')
    args = parser.parse_args(argv)
    try:
        data = {}
        for key in ('plan', 'parameters', 'decisions_config'):
            path = Path(getattr(args, key))
            if path.resolve() != path.absolute() or path.is_symlink() or not path.is_file():
                raise PlanError('INPUT_PATH_INVALID', 'Canonical regular input files required')
            data[key] = path.read_bytes()
        script, _ = generate_script(data['plan'], expected_plan_sha256=args.plan_sha256,
            parameters_raw=data['parameters'], expected_parameters_sha256=args.parameters_sha256,
            decisions_raw=data['decisions_config'], expected_decisions_sha256=args.decisions_config_sha256,
            plan_path=str(Path(args.plan).absolute()), formal=args.formal)
        with Path(args.output).open('xb') as stream:
            stream.write(v1.canonical(script) + b'\n')
    except PlanError as error:
        parser.exit(2, error.category + ': ' + str(error) + '\n')
    except OSError as error:
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
