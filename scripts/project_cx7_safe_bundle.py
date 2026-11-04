"""Portable safe-only successor to the LOCAL D119 projection helper.

Re-materialize an already projected D119 bundle and its sanitized external
inventories. Never enumerate an event root or access the legacy private inventory.
The existing read-only D119 checker validates both source and copy. Historical
receipt bytes remain unchanged; current copy/disk observations get a separate receipt.
"""
from __future__ import annotations
import json
from pathlib import Path
from r004_local_common import (argv_after_separator, authorize, checked_path, digest, disk,
    execution_options, file_sha, new_output, parser, pinned, read_bytes, require, write_bytes, write_json)


def child(root, name):
    require(isinstance(name, str) and name and '\\' not in name, 'UNSAFE_MANIFEST_PATH')
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == name,
            'UNSAFE_MANIFEST_PATH')
    return checked_path(root / path)


def parse_args(argv=None):
    p = parser(__doc__)
    p.add_argument('--source-bundle', type=Path, required=True, help='Contains safe_bundle/; not an event run root.')
    p.add_argument('--receipt', type=Path, required=True, help='Historical external D119 receipt, outside private namespaces.')
    p.add_argument('--receipt-sha256', required=True)
    p.add_argument('--output', type=Path, required=True, help='New root for bundle/, receipt and sanitized evidence.')
    execution_options(p)
    return p.parse_args(argv_after_separator(argv))


def main(argv=None):
    args = parse_args(argv)
    authorize(args)
    source = checked_path(args.source_bundle)
    source_safe = checked_path(source / 'safe_bundle')
    receipt_path = checked_path(args.receipt)
    receipt_raw = pinned(receipt_path, args.receipt_sha256)
    receipt = json.loads(receipt_raw)
    require(receipt.get('profile') == 'r004-a4b4', 'D119_RECEIPT_REQUIRED')
    inventories = {}
    for scope in receipt['runs']:
        name = scope['source_inventory_ref']
        path = child(receipt_path.parent, name)
        inventories[name] = pinned(path, scope['source_inventory_sha256'])
    from check_event_run_bundle import inspect_bundle
    result = inspect_bundle(source, receipt_path, profile='r004-a4b4')
    require(result.get('status') == 'PASS', 'SOURCE_D119_CHECK_FAILED')
    manifest_raw = pinned(source_safe / 'manifest.json', receipt['safe_manifest_sha256'])
    manifest = json.loads(manifest_raw)
    files = manifest['files']
    # Validate all names before creating output. The checker validates JSON privacy/PNG.
    for name in files:
        child(source_safe, name)
    total = len(receipt_raw) + len(manifest_raw) + sum(len(r) for r in inventories.values())
    total += sum(child(source_safe, name).stat().st_size for name in files)
    before = disk(args.output, total)
    out = new_output(args.output)
    safe = out / 'bundle/safe_bundle'
    for name, pin in files.items():
        original = child(source_safe, name)
        raw = pinned(original, pin)
        target = child(safe, name)
        write_bytes(target, raw)
        require(file_sha(original) == pin and file_sha(target) == pin, 'COPY_PIN_MISMATCH')
    write_bytes(safe / 'manifest.json', manifest_raw)
    for name, raw in inventories.items():
        write_bytes(child(out, name), raw)
    write_bytes(out / 'receipt.json', receipt_raw)
    checked = inspect_bundle(out / 'bundle', out / 'receipt.json', profile='r004-a4b4')
    require(checked.get('status') == 'PASS', 'COPY_D119_CHECK_FAILED')
    after = disk(out)
    write_json(out / 'projection-copy-receipt.json', {'status': 'COPIED_AND_D119_CHECKED',
        'source_receipt_sha256': digest(receipt_raw), 'safe_manifest_sha256': digest(manifest_raw),
        'copied_files': len(files) + 1 + len(inventories) + 1,
        'before_available_bytes': before, 'after_available_bytes': after,
        'method': 'independent regular files; no hardlinks; source and target hashes checked',
        'historical_receipt_reused_as_history': True, 'human_approval_verified': False,
        'production_contract': 'UNSELECTED', 'allowed_purposes': []})


if __name__ == '__main__':
    main()
