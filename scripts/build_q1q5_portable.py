"""Build LOCAL P1 viewer data; code/docs only go on GitHub."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from amidst.q1q5.portable_pack import build
from amidst.q1q5.production_preflight import read_pinned, strict_json


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--code-commit',required=True)
    for name in ['rgb','registry','recordings']:
        p.add_argument('--'+name,type=Path,required=True);p.add_argument('--'+name+'-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv);before=subprocess.check_output(['df','-k',str(a.output.parent)],text=True)
    spec=strict_json(read_pinned(a.recordings,a.recordings_sha256));started=time.perf_counter()
    if spec['schema_version']!='q-demo.portable-source-recordings.v1':p.error('pinned source-recordings list required')
    receipt=build(a.repo,a.code_commit,a.rgb,a.rgb_sha256,a.registry,a.registry_sha256,spec['recordings'],a.output)
    receipt.update(build_latency_ms=(time.perf_counter()-started)*1000,df_before=before,
        df_after=subprocess.check_output(['df','-k',str(a.output)],text=True),python_version=sys.version.split()[0])
    sidecar=a.output.with_name(a.output.name+'.build-receipt.json')
    if sidecar.exists():raise FileExistsError('build sidecar must be new')
    sidecar.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));return 0


if __name__=='__main__':raise SystemExit(main())
