"""Generate a `q5-evaluation-script.v1` from a script plan after the pre-checks (evaluation-only)."""
import argparse
from pathlib import Path

from amidst.evaluation.q5_script_adapter import PlanError, dumps, generate_script, load_plan, precheck


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', help='new script file (never overwritten)')
    parser.add_argument('--report', help='new pre-check report file (never overwritten)')
    parser.add_argument('--formal', action='store_true', help='refuse UNKNOWN run/clock and unfrozen plans')
    args = parser.parse_args(argv)
    try:
        plan = load_plan(Path(args.plan).read_bytes())
        report = precheck(plan)
        if args.report:
            with Path(args.report).open('x', encoding='utf-8') as stream:
                stream.write(dumps(report))
        script = generate_script(plan, formal=args.formal)
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as stream:
                stream.write(dumps(script))
    except PlanError as exc:
        parser.exit(2, 'REJECTED:\n' + str(exc) + '\n')
    except OSError as exc:
        parser.exit(2, str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
