"""Regenerate the portable file ledger from the retained LOCAL copy receipt."""
import argparse
import hashlib
import json
from pathlib import Path


def export(root):
    raw = (root/'copy-manifest.json').read_bytes(); original = json.loads(raw); rows = []
    for entry in original['files']:
        row = {k: entry[k] for k in ('group', 'bytes', 'kind')}; row['path'] = entry['destination']
        for key in ('sha256', 'target'):
            if key in entry:
                row[key] = entry[key]
        if entry['group'] == 'PYTHON':
            row['platform'] = 'darwin-arm64'
        rows.append(row)
    job = (root/'metadata/cross-camera-job.json').read_bytes()
    rows.append({'group': 'OWNED_JOB', 'path': 'metadata/cross-camera-job.json', 'kind': 'file',
                 'bytes': len(job), 'sha256': hashlib.sha256(job).hexdigest()})
    groups = {g: {'entries': sum(r['group'] == g for r in rows), 'bytes': sum(r['bytes'] for r in rows if r['group'] == g)}
              for g in sorted({r['group'] for r in rows})}
    return (json.dumps({'schema_version': 'amidst.demo-owned-files.v1', 'source_head': original['source_head'],
                       'copy_receipt_sha256': hashlib.sha256(raw).hexdigest(), 'source_mutations': False,
                       'groups': groups, 'files': rows}, indent=2)+'\n').encode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owned-root', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); data = export(args.owned_root)
    # An existing output is accepted only when the bytes are already identical.
    if args.output.exists():
        if args.output.read_bytes() != data:
            raise SystemExit('EXISTING_MANIFEST_DIFFERS')
    else:
        with args.output.open('xb') as stream:
            stream.write(data)
    print(hashlib.sha256(data).hexdigest())
