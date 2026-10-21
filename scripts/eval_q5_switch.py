"""Freeze and verify Q5 outputs before reading an evaluation-only script."""
import argparse
from pathlib import Path
from amidst.evaluation.q5_switch_eval import EvaluationError,canonical,freeze_output,compare_script


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['response','response-sha256','decisions','decisions-sha256','script','script-sha256','output']:
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    try:
        # Deliberate ordering: an invalid/unfrozen output never opens the script.
        frozen=freeze_output(Path(args.response).read_bytes(),Path(args.decisions).read_bytes(),
                             expected_response_sha256=args.response_sha256,expected_decisions_sha256=args.decisions_sha256)
        report=compare_script(frozen,Path(args.script).read_bytes(),expected_script_sha256=args.script_sha256)
        with Path(args.output).open('xb') as stream:stream.write(canonical(report)+b'\n')
    except (EvaluationError,OSError,ValueError,TypeError,KeyError) as exc:
        parser.exit(2,str(exc)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
