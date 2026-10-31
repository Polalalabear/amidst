"""Check mapped demo steps and required columns, without runtime execution."""
import argparse
import json
from demo_record_checks import CheckError, check_script, read


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script',required=True);parser.add_argument('--checklist',required=True)
    args=parser.parse_args(argv)
    try:
        report=check_script(read(args.script),read(args.checklist))
    except (CheckError,OSError) as error:
        parser.exit(2,str(error)+'\n')
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
