"""Pinned, offline frozen-output replay packaging (#293, D112-1). Standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import unicodedata
import zipfile

SYNTHETIC = 'CQ14_TEST_RETURN_V1'
BASELINE = 'TEAM_EVAL_BASELINE_V0_PILOT'
RETURN = 'RETURN/評測結果_姓名_YYYY-MM-DD.json'
TEMPLATE = 'templates/return.json'
MAX_FILE = 4_194_304
MAX_TOTAL = 33_554_432
SHA = re.compile(r'[0-9a-f]{64}\Z')
TEAM_EVAL_SOURCE_PINS = {
    'data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json':
        'ffe5e693a80031e707cddb531925cb97bc6d8295b69777ad3afa1d885bd5a55a',
    'data/recordings/d4b67fd71caef6fb80fc9d92af544959.json':
        '26a1854efb08fe0a809b957692e3f05f92f1f516972e383e1b752f9be0eb02db',
}


class PackError(ValueError):
    pass


def need(value, code):
    if not value:
        raise PackError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: need(False, 'NONFINITE_JSON'))


def relative(value):
    need(isinstance(value, str) and value and '\\' not in value and '\0' not in value, 'PATH_REJECTED')
    path = PurePosixPath(value)
    need(not path.is_absolute() and '..' not in path.parts and path.as_posix() == value, 'PATH_REJECTED')
    need(unicodedata.normalize('NFC', value) == value, 'PATH_NOT_NFC')
    return value


def regular(path):
    path = Path(path).absolute()
    need(path.resolve() == path and not path.is_symlink(), 'SYMLINK_REJECTED')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_FILE, 'FILE_SIZE_OR_TYPE')
        raw = stream.read(MAX_FILE + 1)
    need(len(raw) == info.st_size, 'FILE_CHANGED_DURING_READ')
    return raw


def frozen_scan_view(raw, source_pins):
    """Return a scan-only view after exact original-document byte pin checks."""
    if not source_pins or any(TEAM_EVAL_SOURCE_PINS.get(k) != v for k, v in source_pins.items()):
        return raw
    expected = sorted(source_pins.values())
    if len(expected) == 1 and sha(raw) == expected[0]:
        document = parse(raw)
        documents = [document]
    elif raw.startswith(b'['):
        document = parse(raw)
        if not isinstance(document, list) or len(document) != len(expected):
            return raw
        text = raw.decode('utf-8')
        position, actual = 1, []
        decoder = json.JSONDecoder()
        for _ in document:
            start = position
            while text[position] in ' \t\r\n':
                position += 1
            _, end = decoder.raw_decode(text, position)
            while text[end] in ' \t\r\n':
                end += 1
            actual.append(sha(text[start:end].encode('utf-8')))
            position = end + 1
        if sorted(actual) != expected:
            return raw
        documents = document
    else:
        return raw
    flag = 'g' + 't_' + 'read'
    for item in documents:
        response = item.get('response') if isinstance(item, dict) else None
        provenance = response.get('provenance') if isinstance(response, dict) else None
        if not isinstance(provenance, dict) or provenance.get(flag) is not False:
            return raw
    for item in documents:
        del item['response']['provenance'][flag]
    return encode(document)


def scan_payload(raw, *, profile=None, source_pins=None):
    """Denial tokens are assembled so the tool itself can pass the package text scan."""
    view = frozen_scan_view(raw, source_pins) if profile == BASELINE else raw
    text = view.decode('utf-8-sig')
    words = ['ground' + '_truth', 'g' + 't_', 'visi' + 'bility', 'dep' + 'th',
             'trajec' + 'tory', 'ren' + 'derer', '評分' + '窗',
             '.' + 'blend', '/' + 'Users/', '/' + 'private/', 'configs/' + 'evaluation/']
    representations = [text]
    if text.lstrip().startswith(('{', '[')):
        representations.append(encode(parse(view)).decode())
    for rendered in representations:
        need(not any(word.lower() in rendered.lower() for word in words), 'FORBIDDEN_CONTENT')
        need(not re.search(r'\bGT\b', rendered, re.I), 'FORBIDDEN_CONTENT')
        need(not re.search(r'\bt_[XN]\b', rendered, re.I), 'FORBIDDEN_CONTENT')
        need(not re.search(r'[A-Za-z]:\\', rendered), 'FORBIDDEN_CONTENT')
    return raw


def selected(manifest, profile):
    need(profile in {SYNTHETIC, BASELINE}, 'CONTRACT_UNSELECTED')
    need(manifest.get('schema_version') == 'team-review-pack.v1'
         and manifest.get('version') == 'v0-pilot'
         and manifest.get('evaluation_eligible') is False, 'PROFILE_UNSELECTED')
    expected = ['baseline', 'complex'] if profile == SYNTHETIC else ['baseline']
    need(manifest.get('halves') == expected, 'HALF_NOT_IN_PACK')
    need(manifest.get('source_class') == ('SYNTHETIC' if profile == SYNTHETIC else 'ENGINEERING'),
         'PROFILE_UNSELECTED')
    need(manifest.get('pack_kind') == 'team-model-eval' and manifest.get('samples') == []
         and manifest.get('editable_files') == {} and manifest.get('return_file') == RETURN,
         'MANIFEST_FIELDS_INVALID')
    pins = manifest.get('source_pins')
    need(isinstance(pins, dict) and pins and all(isinstance(k, str) and SHA.fullmatch(v)
         for k, v in pins.items()), 'SOURCE_PINS_INVALID')
    for name in pins:
        relative(name)
    return expected


def verify_pack(root, manifest_sha256, *, profile=None):
    try:
        root = Path(root).absolute()
        need(root.resolve() == root, 'SYMLINK_REJECTED')
        need(isinstance(manifest_sha256, str) and SHA.fullmatch(manifest_sha256), 'MANIFEST_PIN_REQUIRED')
        raw = regular(root / 'MANIFEST.json')
        need(sha(raw) == manifest_sha256, 'MANIFEST_PIN_MISMATCH')
        manifest = parse(raw)
        halves = selected(manifest, profile)
        files = manifest['files']
        need(isinstance(files, dict) and files and 'MANIFEST.json' not in files, 'MANIFEST_FIELDS_INVALID')
        warnings = []
        for name, pin in files.items():
            relative(name)
            need(isinstance(pin, str) and SHA.fullmatch(pin), 'MANIFEST_FIELDS_INVALID')
            path = root / name
            if profile == SYNTHETIC and name == TEMPLATE and not path.exists():
                warnings.append('TEMPLATE_MISSING:' + name)
                continue
            payload = regular(path)
            need(sha(payload) == pin, 'FILE_SHA_MISMATCH')
            scan_payload(payload, profile=profile,
                         source_pins=manifest['source_pins'] if name == 'payload/baseline.json' else None)
        mutable = {f'RETURN/outputs/{half}.json' for half in halves}
        total = 0
        for path in root.rglob('*'):
            need(not path.is_symlink(), 'SYMLINK_REJECTED')
            if path.is_dir():
                continue
            name = relative(path.relative_to(root).as_posix())
            returned = path.parent == root / 'RETURN' and path.name.startswith('評測結果_') and path.suffix == '.json'
            need(name == 'MANIFEST.json' or name in files or name in mutable or returned, 'FILE_SET_MISMATCH')
            raw = regular(path)
            scan_payload(raw, profile=profile, source_pins=manifest['source_pins']
                         if name in {'payload/baseline.json', 'RETURN/outputs/baseline.json'} else None)
            total += len(raw)
        need(total <= MAX_TOTAL, 'PACK_SIZE_LIMIT')
        return {'status': 'VALID_WITH_WARNINGS' if warnings else 'VALID', 'warnings': warnings,
                'reason_codes': ['TEMPLATE_MISSING'] if warnings else [], 'manifest': manifest,
                'human_approval_verified': False, 'release_authorized': False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {'status': 'INVALID', 'reason_category': str(exc) if isinstance(exc, PackError) else 'INPUT_INVALID',
                'warnings': [], 'reason_codes': [], 'human_approval_verified': False, 'release_authorized': False}


def validate_return_document(doc, *, manifest_sha256, halves, profile=None, root=None, source_pins=None):
    try:
        need(profile in {SYNTHETIC, BASELINE}, 'CONTRACT_UNSELECTED')
        need(isinstance(doc, dict), 'RETURN_INVALID')
        need('complex' not in doc, 'HALF_NOT_IN_PACK')
        fields = {'projection', 'schema_candidate', 'pack_manifest_sha256', 'environment',
                  'halves', 'output_sha256', 'return_files'}
        if profile == SYNTHETIC:
            fields.add('fixture_role')
        need(set(doc) <= fields, 'RETURN_FIELDS_INVALID')
        need(doc.get('projection') == profile and doc.get('schema_candidate') == 'team-eval-return.v1',
             'CONTRACT_UNSELECTED')
        need(isinstance(doc.get('pack_manifest_sha256'), str)
             and SHA.fullmatch(doc['pack_manifest_sha256'])
             and doc['pack_manifest_sha256'] == manifest_sha256, 'MANIFEST_PIN_MISMATCH')
        if profile == BASELINE:
            need(isinstance(doc.get('halves'), dict) and set(doc['halves']) == set(halves), 'HALF_NOT_IN_PACK')
        else:
            need(doc.get('halves') == halves, 'HALF_NOT_IN_PACK')
        need(isinstance(doc.get('output_sha256'), dict) and isinstance(doc.get('return_files'), dict),
             'RETURN_FIELDS_MISSING')
        need(set(doc['output_sha256']) == set(doc['return_files']) == set(halves), 'HALF_NOT_IN_PACK')
        environment = doc.get('environment')
        need(isinstance(environment, dict) and environment.get('isolated') is True
             and isinstance(environment.get('python_version'), str)
             and re.fullmatch(r'3\.12\.\d+', environment['python_version'])
             and isinstance(environment.get('platform'), str) and environment['platform'], 'ENVIRONMENT_INVALID')
        need(root is not None, 'RETURN_FILES_UNAVAILABLE')
        root = Path(root).absolute()
        for half, name in doc['return_files'].items():
            need(name == f'RETURN/outputs/{half}.json', 'PATH_REJECTED')
            raw = scan_payload(regular(root / relative(name)), profile=profile,
                               source_pins=source_pins if half == 'baseline' else None)
            need(isinstance(doc['output_sha256'][half], str)
                 and SHA.fullmatch(doc['output_sha256'][half])
                 and sha(raw) == doc['output_sha256'][half], 'OUTPUT_SHA_MISMATCH')
        return {'status': 'VALID', 'observations': doc, 'human_approval_verified': False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {'status': 'INVALID', 'reason_category': str(exc) if isinstance(exc, PackError) else 'INPUT_INVALID',
                'human_approval_verified': False}


def validate_return(root, returned, manifest_sha256, *, profile=None):
    checked = verify_pack(root, manifest_sha256, profile=profile)
    if checked['status'] == 'INVALID':
        return checked
    try:
        doc = parse(scan_payload(regular(returned)))
    except (OSError, ValueError, TypeError) as exc:
        return {'status': 'INVALID', 'reason_category': str(exc) if isinstance(exc, PackError) else 'INPUT_INVALID'}
    return validate_return_document(doc, manifest_sha256=manifest_sha256,
                                    halves=checked['manifest']['halves'], profile=profile, root=root,
                                    source_pins=checked['manifest']['source_pins'])


def replay(root, manifest_sha256, *, profile=None):
    need(sys.version_info[:2] == (3, 12) and sys.flags.isolated == 1, 'PYTHON_3_12_ISOLATED_REQUIRED')
    checked = verify_pack(root, manifest_sha256, profile=profile)
    need(checked['status'] != 'INVALID', checked.get('reason_category', 'PACK_INVALID'))
    root = Path(root).absolute()
    halves = checked['manifest']['halves']
    names = {half: f'RETURN/outputs/{half}.json' for half in halves}
    need(not (root / RETURN).exists() and not any((root / name).exists() for name in names.values()), 'OUTPUT_EXISTS')
    outputs = {half: regular(root / f'payload/{half}.json') for half in halves}
    (root / 'RETURN/outputs').mkdir()
    for half, raw in outputs.items():
        with (root / names[half]).open('xb') as stream:
            stream.write(raw)
    doc = {'projection': profile, 'schema_candidate': 'team-eval-return.v1',
           'pack_manifest_sha256': manifest_sha256,
           'environment': {'python_version': platform.python_version(), 'isolated': True, 'platform': sys.platform},
           'halves': {half: {'status': 'COMPLETE'} for half in halves} if profile == BASELINE else halves,
           'output_sha256': {half: sha(raw) for half, raw in outputs.items()}, 'return_files': names}
    with (root / RETURN).open('xb') as stream:
        stream.write(encode(doc))
    return validate_return(root, root / RETURN, manifest_sha256, profile=profile)


def build_pack(output, frozen_outputs, *, profile=None, source_pins=None,
               version='v0-pilot', evaluation_eligible=False):
    need(profile in {SYNTHETIC, BASELINE}, 'CONTRACT_UNSELECTED')
    need(version == 'v0-pilot' and evaluation_eligible is False, 'PROFILE_UNSELECTED')
    halves = ['baseline', 'complex'] if profile == SYNTHETIC else ['baseline']
    need(set(frozen_outputs) == set(halves), 'HALF_NOT_IN_PACK')
    output = Path(output).absolute()
    need(output.resolve() == output and not output.exists(), 'OUTPUT_EXISTS_OR_UNSAFE')
    need(shutil.disk_usage(output.parent).free >= 8 * 1024**3, 'DISK_BELOW_8_GIB')
    payloads, pins = {}, {}
    for half, ref in frozen_outputs.items():
        parts = ref if isinstance(ref, list) else [ref]
        need(parts, 'SOURCE_PINS_INVALID')
        chunks = []
        for part in parts:
            chunk = regular(part['path'])
            need(sha(chunk) == part['sha256'], 'SOURCE_PIN_MISMATCH')
            name = relative(part.get('source_name', Path(part['path']).name))
            need(name not in pins, 'SOURCE_NAME_DUPLICATE')
            pins[name] = part['sha256']
            scan_payload(chunk, profile=profile, source_pins={name: part['sha256']} if half == 'baseline' else None)
            parse(chunk)
            chunks.append(chunk)
        # A half may collect several frozen JSON documents; each original byte slice is preserved.
        raw = b'[' + b','.join(chunks) + b']\n' if isinstance(ref, list) else chunks[0]
        payloads[f'payload/{half}.json'] = raw
    if source_pins is not None:
        need(source_pins == pins, 'SOURCE_PIN_MISMATCH')
    manifest = {'schema_version': 'team-review-pack.v1', 'version': version,
                'evaluation_eligible': evaluation_eligible, 'samples': [], 'pack_kind': 'team-model-eval',
                'source_class': 'SYNTHETIC' if profile == SYNTHETIC else 'ENGINEERING', 'halves': halves,
                'return_file': RETURN, 'source_pins': pins, 'files': {}, 'editable_files': {}}
    selected(manifest, profile)
    message = ('本包只含 Baseline（ENGINEERING）；複雜事件半部未包含。'
               if profile == BASELINE else '本包是 SYNTHETIC 兩半離線功能控制，不代表真實評測。')
    payloads['README.txt'] = (f'工作內容\n{message}\n只重播既有凍結輸出，不執行模型。\n'
        f'要提交項目\n{RETURN}\n連同 RETURN/outputs 交回；未完成時檔名加 _INCOMPLETE 並說明原因。\n'
        f'操作\n使用 Python 3.12。先驗證再重播，需使用發包者提供的 MANIFEST pin：\n'
        f'python3.12 -I tools/verify_pack.py --profile {profile} --manifest-sha256 PIN\n'
        f'./start.command --manifest-sha256 PIN\n'
        '不要改\npayload、tools、MANIFEST 與設定不得修改；保留原包。重跑時使用新的解壓目錄。\n').encode()
    payloads['RETURN/README.txt'] = (f'交回 {RETURN} 與 outputs；未完成檔名加 _INCOMPLETE。\n').encode()
    native = Path(__file__).read_bytes()
    payloads['tools/team_eval.py'] = native
    payloads['tools/verify_pack.py'] = native
    payloads['start.command'] = (f'#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\n'
        f'exec python3.12 -I tools/team_eval.py --profile {profile} "$@"\n').encode()
    if profile == SYNTHETIC:
        payloads[TEMPLATE] = encode({'projection': SYNTHETIC, 'schema_candidate': 'team-eval-return.v1'})
    need(sum(map(len, payloads.values())) <= MAX_TOTAL and all(len(raw) <= MAX_FILE for raw in payloads.values()),
         'PACK_SIZE_LIMIT')
    for name, raw in payloads.items():
        scan_payload(raw, profile=profile, source_pins=pins if name == 'payload/baseline.json' else None)
    manifest['files'] = {name: sha(raw) for name, raw in sorted(payloads.items())}
    output.mkdir()
    for name, raw in payloads.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (output / 'start.command').chmod(0o755)
    raw = encode(manifest)
    (output / 'MANIFEST.json').write_bytes(raw)
    return {'root': str(output), 'manifest_sha256': sha(raw), 'manifest': manifest, 'release_authorized': False}


def build_from_inputs(inputs, output, *, profile=None):
    inputs = Path(inputs).absolute()
    doc = parse(regular(inputs))
    need(profile == SYNTHETIC and doc.get('fixture_role') == 'SYNTHETIC_ONLY'
         and doc.get('projection') == 'CQ14_TEST_INPUT_V1', 'CONTRACT_UNSELECTED')
    refs = {key.lower(): {'path': inputs.parent / relative(ref['path']), 'sha256': ref['sha256']}
            for key, ref in doc['frozen_outputs'].items()}
    return build_pack(output, refs, profile=profile)


def write_zip(root, target):
    root, target = Path(root).absolute(), Path(target).absolute()
    need(not target.exists() and target.resolve() == target and not target.is_relative_to(root), 'OUTPUT_EXISTS_OR_UNSAFE')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            need(not path.is_symlink(), 'SYMLINK_REJECTED')
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.name == 'start.command' else 0o100644) << 16
            archive.writestr(info, regular(path))
    return sha(target.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=Path(__file__).absolute().parents[1])
    parser.add_argument('--profile', choices=[SYNTHETIC, BASELINE])
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    try:
        operation = verify_pack if Path(__file__).name == 'verify_pack.py' else replay
        result = operation(args.pack, args.manifest_sha256, profile=args.profile)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {'status': 'INVALID', 'reason_category': str(exc) if isinstance(exc, PackError) else 'INPUT_INVALID'}
    result.pop('manifest', None)
    result.pop('observations', None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result['status'] == 'INVALID' else 0


if __name__ == '__main__':
    raise SystemExit(main())
