"""CQ-42-T format checks only; no runtime, authority, media or GT readers."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

SCHEMAS = Path(__file__).resolve().parents[1] / 'docs/agents/schemas'
REVIEW = 'NOT_REVIEWED'


class CheckError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise CheckError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    need(path.resolve() == path.absolute() and path.is_file() and not path.is_symlink(), 'Canonical regular file required')
    return path.read_bytes()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise CheckError('Non-finite JSON value')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as error:
        raise CheckError('Malformed JSON: ' + str(error)) from error


def schema_check(value, schema, location='$'):
    """Validate exactly the small, closed subset used by the two local schemas.

    Unsupported schema keywords fail closed. This is not a general JSON Schema
    implementation and never loads a remote $schema or $ref.
    """
    supported = {'$schema','description','type','properties','required','additionalProperties',
                 'items','minItems','maxItems','minLength','pattern','enum','const','default'}
    need(set(schema) <= supported, 'Unsupported local schema keyword')
    if 'const' in schema:
        need(type(value) is type(schema['const']) and value == schema['const'], location + ': wrong version/constant')
    if 'enum' in schema:
        need(any(type(value) is type(v) and value == v for v in schema['enum']), location + ': invalid enum')
    kind = schema.get('type')
    if kind == 'object':
        need(isinstance(value, dict), location + ': object required')
        props = schema['properties']
        need(set(schema.get('required', [])) <= value.keys(), location + ': missing required field')
        need(schema.get('additionalProperties') is False and value.keys() <= props.keys(), location + ': unknown field')
        for key, item in value.items():
            schema_check(item, props[key], location + '.' + key)
    elif kind == 'array':
        need(isinstance(value, list), location + ': array required')
        need(schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', len(value)), location + ': wrong item count')
        for i, item in enumerate(value):
            schema_check(item, schema['items'], location + '[' + str(i) + ']')
    elif kind == 'string':
        need(isinstance(value, str), location + ': string required')
        need(len(value.strip()) >= schema.get('minLength', 0), location + ': empty string')
        if 'pattern' in schema:
            need(re.fullmatch(schema['pattern'], value) is not None, location + ': invalid format')
    else:
        need(kind is None and ('const' in schema or 'enum' in schema), 'Unsupported local schema type')


FORBIDDEN_KEY = re.compile(r'^(?:gt(?:_.*)?|ground_truth|t_[xn](?:_us)?|decision_window(?:_us)?|entry_windows?(?:_us)?|plan_anchor_us|renderer.*|trajectory.*|visibility|depth)$', re.I)
FORBIDDEN_VALUE = re.compile(r'(?:\b(?:t_?[XN](?:_us)?|gt(?:_[a-z]\w*)?|ground[_ ]truth|decision_window(?:_us)?|entry_windows?(?:_us)?|renderer[_ ]trajectory|visibility|depth)\b|評分窗|劇本時刻)\s*["\']?\s*(?:[:=：]\s*)?(?:[\[(]\s*)?[-+]?\d', re.I)


def no_private_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            need(FORBIDDEN_KEY.fullmatch(unicodedata.normalize('NFKC', key)) is None, 'Private evaluation/GT field refused')
            no_private_values(item)
    elif isinstance(value, list):
        for item in value:
            no_private_values(item)
    elif isinstance(value, str):
        text = unicodedata.normalize('NFKC', value).replace('`', '')
        need(FORBIDDEN_VALUE.search(text) is None, 'Private evaluation/GT timing value refused')


def checklist(raw):
    doc = decode(raw)
    schema_check(doc, decode(read(SCHEMAS/'demo-checklist.v1.json')))
    no_private_values(doc)
    ids = [row['id'] for row in doc['items']]
    need(len(ids) == len(set(ids)), 'Duplicate checklist ID')
    return doc, ids


def check_record(record_raw, checklist_raw):
    _, ids = checklist(checklist_raw)
    doc = decode(record_raw)
    schema_check(doc, decode(read(SCHEMAS/'demo-rehearsal-record.v1.json')))
    no_private_values(doc)
    need(doc['checklist_sha256'] == sha(checklist_raw), 'Checklist byte pin mismatch')
    rows = doc['items']; actual = [row['id'] for row in rows]
    need(len(actual) == len(set(actual)), 'Duplicate rehearsal item ID')
    need(set(actual) == set(ids), 'Rehearsal items must exactly cover checklist IDs')
    fallback = [row['id'] for row in doc['fallback']]
    need(len(fallback) == len(set(fallback)) and set(fallback) == set('abc'), 'Fallback a/b/c records required exactly once')
    for row in rows + doc['fallback']:
        need(row['result'] != 'PASS' or bool(row['evidence']), 'PASS requires screenshot/output SHA-256 evidence')
    need(all(row['result'] != 'NOT_RUN' for row in doc['fallback']), 'Fallback a/b/c must have rehearsal records, not NOT_RUN')
    return {'validation': 'VALID_RECORD_FORMAT', 'record_file_sha256': sha(record_raw),
        'checklist_file_sha256': sha(checklist_raw), 'item_count': len(ids),
        'result_counts': {status: sum(r['result'] == status for r in rows) for status in ('PASS','FAIL','NOT_RUN')},
        'claude_review_status_reported': {r['id']: r.get('claude_review_status',REVIEW) for r in rows},
        'fallback_results_reported': {r['id']: r['result'] for r in doc['fallback']},
        'fallback_claude_review_status_reported': {r['id']: r.get('claude_review_status',REVIEW) for r in doc['fallback']},
        'evidence_hashes': 'REPORTED_ONLY_NOT_READ_OR_VERIFIED',
        'human_acceptance_verified': False, 'claude_review_verified': False,
        'limits': ['Format completeness is not demo success or #346 acceptance.',
                   'Evidence hashes are checked for presence/format; evidence bytes and actual operation remain unverified.']}


def check_script(script_raw, checklist_raw):
    _, ids = checklist(checklist_raw)
    try:
        text = script_raw.decode('utf-8')
    except UnicodeError as error:
        raise CheckError('UTF-8 script required') from error
    no_private_values(text)
    steps, current = [], None
    for line in text.splitlines():
        if re.match(r'^##\s', line):
            match = re.fullmatch(r'##\s+([BCD]-[0-9]{2})(?:\s+.*)?', line)
            need(match is not None, 'Step heading must be ## B-01/C-01/D-01 plus optional title')
            current = {'id': match[1], 'fields': {}}; steps.append(current)
        field = re.match(r'^\s*(?:[-*]\s*)?(操作|預期|fallback)\s*[:：]\s*(.*)$', line)
        if field:
            need(current is not None, 'Step field outside a step')
            name, value = field.groups()
            need(name not in current['fields'] and bool(value.strip()), 'Missing/duplicate/empty step column')
            current['fields'][name] = value
    need(bool(steps), 'Nonempty demo step list required')
    step_ids = [step['id'] for step in steps]
    need(len(step_ids) == len(set(step_ids)), 'Duplicate demo step ID')
    need(set(step_ids) <= set(ids), 'Unknown checklist ID in demo script')
    need(all(set(step['fields']) == {'操作','預期','fallback'} for step in steps), 'Each step needs 操作, 預期 and fallback')
    return {'validation': 'VALID_SCRIPT_FORMAT', 'script_file_sha256': sha(script_raw),
        'checklist_file_sha256': sha(checklist_raw), 'step_ids': step_ids,
        'uncovered_checklist_ids': [i for i in ids if i not in step_ids],
        'claude_review_status': REVIEW, 'human_acceptance_verified': False,
        'limits': ['Every listed step is mapped; this does not prove browser execution or full demo coverage.',
                   'The private-data check rejects named fields/assignments, not arbitrary semantic paraphrases.']}
