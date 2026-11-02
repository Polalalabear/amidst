#!/usr/bin/env python3
"""Read-only handoff integrity checker. Extended workflows require selected inputs.

Standalone standard library tool; never execute a verifier supplied by a pack.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import unicodedata
import zipfile

VERSION = "cq27t-synthetic-v1"
MAX_FILE = 4_194_304
MAX_TOTAL = 33_554_432
MAX_FILES = 2000
TEXT_COLUMNS = ['編號','使用者會說的話','想找什麼(人/車/相機)','顏色','開始時間','結束時間','鏡頭或區域','系統該反問嗎(是/否)','預期結果(找得到/找不到/不支援/超出時間/反問)','備註']
REVIEW_COLUMNS = ['樣本編號','圖檔','系統說法(例：這格有紅衣人／這格有車／這格沒有人)','答案(T/F/不確定)','備註']
TEXT_FILE = 'A_文字情境/情境.csv'
REVIEW_FILE = 'B_畫面審查/審查表.csv'
TEMPLATES = {'templates/情境.csv', 'templates/審查表.csv'}
# Assemble scanner tokens so this standalone tool can be scanned like all payloads.
BAD_TEXT = re.compile('|'.join([
    r'\bt_[XNVL]\b', r'\b(?:decision|entry|scoring|score)_?window(?:_[a-z]+)?\b',
    re.escape('configs/' + 'evaluation/'), re.escape('_script_' + 'plan_'),
    re.escape('-'.join(['q5', 'evaluation', 'script'])), re.escape('_' + 'RECEIPT'),
    re.escape('.' + 'blend'), re.escape('/' + 'Users/'), re.escape('/' + 'private/'),
    re.escape('~/' + 'amidst-artifacts')]), re.I)
BAD_KEY = re.compile(r'(?:^|[^a-z])(?:gt|trajectory|visibility|depth)(?:$|[^a-z])', re.I)
KEY_TEXT = re.compile(r'''["']([^"'\r\n]+)["']\s*:''')
SHA = re.compile(r'[0-9a-f]{64}')


class PackCheckError(ValueError):
    pass


def need(value, code):
    if not value:
        raise PackCheckError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def invalid(_):
        raise PackCheckError('NONFINITE_JSON')
    doc = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    json.dumps(doc, allow_nan=False)
    return doc


def name_ok(name):
    need(isinstance(name, str) and name and '\\' not in name and '\0' not in name, 'PATH_REJECTED')
    need(unicodedata.normalize('NFC', name) == name, 'NAME_NOT_NFC')
    path = PurePosixPath(name)
    need(not path.is_absolute() and path.as_posix() == name and '..' not in path.parts, 'PATH_REJECTED')
    need(not any(part in {'.DS_Store', '__pycache__'} for part in path.parts), 'EXCLUDED_FILE_PRESENT')
    return name


def regular(path, maximum=MAX_FILE):
    path = Path(path).absolute()
    need(path.resolve() == path, 'SYMLINK_REJECTED')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= maximum, 'FILE_SIZE_OR_TYPE')
        raw = stream.read(maximum + 1)
    need(len(raw) == info.st_size, 'FILE_CHANGED_DURING_READ')
    return raw


def load_files(pack, zip_timestamp):
    pack = Path(pack).absolute()
    need(pack.resolve() == pack, 'SYMLINK_REJECTED')
    result = {}
    if pack.is_dir():
        for path in pack.rglob('*'):
            need(not path.is_symlink(), 'SYMLINK_REJECTED')
            name = name_ok(path.relative_to(pack).as_posix())
            need(path.is_dir() or path.is_file(), 'FILE_SIZE_OR_TYPE')
            if path.is_file():
                result[name] = regular(path)
                need(len(result) <= MAX_FILES and sum(map(len, result.values())) <= MAX_TOTAL, 'PACK_SIZE_LIMIT')
    else:
        raw = regular(pack, MAX_TOTAL)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            need(len(infos) <= MAX_FILES and sum(i.file_size for i in infos) <= MAX_TOTAL, 'PACK_SIZE_LIMIT')
            seen = set()
            for info in infos:
                name = name_ok(info.filename.rstrip('/'))
                need(name.casefold() not in seen, 'ZIP_DUPLICATE_NAME')
                seen.add(name.casefold())
                mode = info.external_attr >> 16
                need(not stat.S_ISLNK(mode), 'SYMLINK_REJECTED')
                need(not (info.flag_bits & 1), 'ZIP_ENCRYPTED')
                need(list(info.date_time) == zip_timestamp, 'ZIP_TIMESTAMP_MISMATCH')
                if not info.filename.isascii():
                    local_flags = struct.unpack_from('<H', raw, info.header_offset + 6)[0]
                    need(info.flag_bits & 0x800 and local_flags & 0x800, 'ZIP_UTF8_FLAG_MISSING')
                    length = struct.unpack_from('<H', raw, info.header_offset + 26)[0]
                    need(raw[info.header_offset + 30:info.header_offset + 30 + length]
                         == info.filename.encode('utf-8'), 'ZIP_NAME_CHANGED')
                if not info.is_dir():
                    need(info.file_size <= MAX_FILE, 'FILE_SIZE_OR_TYPE')
                    result[name] = archive.read(info)
        if 'MANIFEST.json' not in result:
            candidates = [n for n in result if n.endswith('/MANIFEST.json')]
            need(len(candidates) == 1, 'MANIFEST_MISSING')
            prefix = candidates[0][:-len('MANIFEST.json')]
            need(all(n.startswith(prefix) for n in result), 'ZIP_ROOT_MISMATCH')
            result = {n[len(prefix):]: data for n, data in result.items()}
    need(len(result) <= MAX_FILES and sum(map(len, result.values())) <= MAX_TOTAL, 'PACK_SIZE_LIMIT')
    need(len({n.casefold() for n in result}) == len(result), 'DUPLICATE_NAME')
    return result


def scan(files):
    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                need(not BAD_KEY.search(key) and not BAD_TEXT.search(key), 'FORBIDDEN_CONTENT')
                keys(child)
        elif isinstance(value, list):
            for child in value:
                keys(child)
        elif isinstance(value, str):
            need(not BAD_TEXT.search(value), 'FORBIDDEN_CONTENT')
    for name, raw in files.items():
        need(not BAD_TEXT.search(name), 'FORBIDDEN_CONTENT')
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeError:
            need(Path(name).suffix.lower() not in {'.json', '.jsonl', '.txt', '.csv', '.py', '.js', '.html', '.md', '.svg'}, 'TEXT_UTF8_REQUIRED')
            continue
        need(not BAD_TEXT.search(text), 'FORBIDDEN_CONTENT')
        need(not any(BAD_KEY.search(m.group(1)) for m in KEY_TEXT.finditer(text)), 'FORBIDDEN_CONTENT')
        if name.endswith('.json'):
            keys(parse(raw))
        elif name.endswith('.jsonl'):
            for line in raw.splitlines():
                if line.strip():
                    keys(parse(line))


def csv_rows(raw, columns, ids):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    need(reader.fieldnames == columns, 'CSV_HEADER_INVALID')
    rows = list(reader)
    need(all(None not in row and all(isinstance(row.get(c), str) for c in columns) for row in rows), 'CSV_ROW_INVALID')
    need([row[columns[0]] for row in rows] == ids, 'CSV_IDS_INVALID')
    return rows


def _inspect(pack, profile, manifest_sha256, options_path, options_sha256, returned_csv):
    need(profile in {'yyin-main', 'team-eval'}, 'PROFILE_UNKNOWN')
    need(options_path is not None and options_sha256 is not None, 'PROFILE_UNSELECTED')
    option_raw = regular(options_path)
    need(sha(option_raw) == options_sha256, 'PROFILE_PIN_MISMATCH')
    options = parse(option_raw)
    need(options.get('fixture_role') == 'SYNTHETIC_ONLY'
         and options.get('projection') == 'SYNTHETIC_HANDOFF_PROFILE_V1'
         and options.get('profile') == profile, 'PROFILE_UNSELECTED')
    phase = options.get('phase', 'S1_S2_SYNTHETIC')
    need(phase in {'S1_S2_SYNTHETIC', 'S2_FRAMEWORK_ONLY'}, 'PROFILE_UNSELECTED')
    timestamp = options.get('zip_timestamp')
    need(isinstance(timestamp, list) and len(timestamp) == 6
         and all(type(value) is int for value in timestamp), 'PROFILE_UNSELECTED')
    files = load_files(pack, timestamp)
    need('MANIFEST.json' in files, 'MANIFEST_MISSING')
    need(isinstance(manifest_sha256, str) and SHA.fullmatch(manifest_sha256)
         and sha(files['MANIFEST.json']) == manifest_sha256, 'MANIFEST_PIN_MISMATCH')
    manifest = parse(files['MANIFEST.json'])
    need(manifest.get('schema_version') == 'team-review-pack.v1'
         and manifest.get('version') in {'v0-pilot', 'v1'}
         and type(manifest.get('evaluation_eligible')) is bool and manifest.get('samples') == [], 'MANIFEST_FIELDS_INVALID')
    declared = manifest.get('files')
    need(isinstance(declared, dict) and declared and 'MANIFEST.json' not in declared, 'MANIFEST_FIELDS_INVALID')
    for name, pin in declared.items():
        name_ok(name)
        need(isinstance(pin, str) and SHA.fullmatch(pin), 'MANIFEST_FIELDS_INVALID')
    missing = set(declared) - files.keys()
    need(not missing - TEMPLATES, 'FILE_MISSING')
    warnings = ['TEMPLATE_MISSING:' + name for name in sorted(missing)]
    need(files.keys() <= declared.keys() | {'MANIFEST.json'}, 'FILE_SET_MISMATCH')
    for name in declared.keys() & files.keys():
        need(sha(files[name]) == declared[name], 'FILE_SHA_MISMATCH')
    scan(files)
    editable = manifest.get('editable_files')
    expected = {TEXT_FILE: ('templates/情境.csv', TEXT_COLUMNS[:1]),
                REVIEW_FILE: ('templates/審查表.csv', REVIEW_COLUMNS[:3])}
    need(isinstance(editable, dict) and set(editable) == set(expected), 'EDITABLE_FILES_INVALID')
    text_ids = options.get('text_ids')
    need(isinstance(text_ids, list) and text_ids and len(text_ids) == len(set(text_ids))
         and all(isinstance(i, str) for i in text_ids), 'PROFILE_UNSELECTED')
    for name, (template, locked) in expected.items():
        need(editable[name] == {'template_ref': template, 'locked_columns': locked}
             and declared.get(template) == declared.get(name), 'TEMPLATE_BINDING_INVALID')
        csv_rows(files[name], TEXT_COLUMNS if name == TEXT_FILE else REVIEW_COLUMNS,
                 text_ids if name == TEXT_FILE else [])
        if template in files:
            need(files[name] == files[template], 'TEMPLATE_BINDING_INVALID')
    if phase == 'S1_S2_SYNTHETIC':
        s1 = options.get('s1')
        need(isinstance(s1, dict) and isinstance(s1.get('columns'), list)
             and isinstance(s1.get('row_ids'), list) and len(s1['row_ids']) == 3, 'PROFILE_UNSELECTED')
        for name in (s1['filename'], s1['template_ref']):
            name_ok(name)
            need(name in files, 'FILE_MISSING')
            csv_rows(files[name], s1['columns'], s1['row_ids'])
        need(files[s1['filename']] == files[s1['template_ref']], 'TEMPLATE_BINDING_INVALID')
    readme_name = name_ok(options.get('readme'))
    need(readme_name in files and 'RETURN/README.txt' in files and 'tools/verify_pack.py' in files, 'README_INCOMPLETE')
    readme = files[readme_name].decode('utf-8-sig')
    returns = options.get('return_names')
    need(isinstance(returns, dict) and set(returns) == ({'s1', 's2'} if phase == 'S1_S2_SYNTHETIC' else {'s2'}), 'PROFILE_UNSELECTED')
    need(all(word in readme for word in ['工作內容', '要提交項目', '操作', '不要改', 's2', '_INCOMPLETE'])
         and (phase != 'S1_S2_SYNTHETIC' or 's1' in readme)
         and all('RETURN/' + name_ok(name) in readme for name in returns.values()), 'README_INCOMPLETE')
    if returned_csv is not None:
        csv_rows(regular(returned_csv), TEXT_COLUMNS, text_ids)
    return {'status': 'VALID_WITH_WARNINGS' if warnings else 'VALID', 'warnings': warnings,
            'file_count': len(files), 'manifest_sha256': manifest_sha256, 'validated_scope': phase,
            'returned_csv_checked': returned_csv is not None}


def inspect_pack(pack, *, profile='yyin-main', manifest_sha256=None, options_path=None, options_sha256=None, returned_csv=None):
    try:
        result = _inspect(pack, profile, manifest_sha256, options_path, options_sha256, returned_csv)
    except PackCheckError as exc:
        result = {'status': 'INVALID', 'code': str(exc), 'warnings': []}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, struct.error, zipfile.BadZipFile):
        result = {'status': 'INVALID', 'code': 'INPUT_INVALID', 'warnings': []}
    return {**result, 'checker_version': VERSION, 'profile': profile, 'human_approval_verified': False,
            'evaluation_eligible_verified': False, 'release_authorized': False,
            'production_profile': 'UNSELECTED', 's0_status': 'UNSELECTED', 'packed_verifier_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=Path(__file__).absolute().parents[1])
    parser.add_argument('--profile', choices=['yyin-main', 'team-eval'], default='yyin-main')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--profile-options', type=Path)
    parser.add_argument('--profile-sha256')
    parser.add_argument('--returned-csv', type=Path)
    args = parser.parse_args()
    result = inspect_pack(args.pack, profile=args.profile, manifest_sha256=args.manifest_sha256,
                          options_path=args.profile_options, options_sha256=args.profile_sha256,
                          returned_csv=args.returned_csv)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result['status'] == 'INVALID' else 0


if __name__ == '__main__':
    raise SystemExit(main())
