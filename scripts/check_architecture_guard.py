#!/usr/bin/env python3
"""Read-only #306/#307 checks. Registration and baseline recognition grant no approval."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


SCHEMA_ROOTS = ('src', 'configs', 'frontend', 'docs/contracts')
TEXT_SUFFIXES = {'.py', '.json', '.jsonl', '.mjs', '.js', '.md', '.html', '.yaml', '.yml', '.txt'}
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'node_modules'}
SCHEMA_LITERAL = re.compile(
    r'''\b(?:["']?schema_version["']?)\s*[:=]\s*["']([^"'\r\n]+)["']''', re.I,
)
SHA = re.compile(r'[0-9a-f]{64}\Z')
ISSUE = re.compile(r'(?:#\d+|https://github\.com/[^/]+/[^/]+/issues/\d+(?:#issuecomment-\d+)?)\Z')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name or '\0' in name:
        raise ValueError('unsafe policy path')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ValueError('unsafe policy path')
    return name


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate policy key')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def source_files(repo, roots, suffixes):
    found = {}
    for root_name in roots:
        root = repo / relative(root_name)
        if any(parent.is_symlink() for parent in root.parents if parent != repo and parent.is_relative_to(repo)):
            raise ValueError('source root has a symlink ancestor')
        if root.is_symlink():
            found[root_name] = root
            continue
        if not root.exists():
            continue
        for path in root.rglob('*'):
            name = path.relative_to(repo).as_posix()
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            if path.suffix.lower() in suffixes and (path.is_file() or path.is_symlink()):
                found[name] = path
    return sorted(found.items())


def authority_check(repo, changed, policy, allowed):
    pins = policy['pins']
    if not isinstance(pins, list) or not pins:
        raise ValueError('authority pins missing')
    by_path = {}
    def contains(ref):
        if not isinstance(ref, str) or not re.fullmatch(r'[0-9a-f]{40}', ref):
            raise ValueError('invalid conditional pin commit')
        probe = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', ref, 'HEAD'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if probe.returncode not in {0, 1}:
            raise ValueError('conditional pin commit unavailable')
        return probe.returncode == 0

    for item in pins:
        name = relative(item['path'])
        if not SHA.fullmatch(item['sha256']) or not item.get('ref') or not item.get('status'):
            raise ValueError('invalid authority pin')
        if item.get('requires_commit') and not contains(item['requires_commit']):
            continue
        if item.get('superseded_by_commit') and contains(item['superseded_by_commit']):
            continue
        if item.get('unchanged_since_commit'):
            original = item['unchanged_since_commit']
            if not isinstance(original, str) or not re.fullmatch(r'[0-9a-f]{40}', original):
                raise ValueError('invalid historical pin baseline')
            probe = subprocess.run(['git', '-C', str(repo), 'diff', '--quiet', original, 'HEAD', '--', name],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if probe.returncode not in {0, 1}:
                raise ValueError('historical pin baseline unavailable')
            if probe.returncode == 1:
                continue
        by_path.setdefault(name, set()).add(item['sha256'])
    findings = []
    for name in sorted(set(allowed) - by_path.keys()):
        findings.append({'code': 'ALLOW_UNKNOWN_PATH', 'path': name})
    for name in sorted(changed & by_path.keys() - set(allowed)):
        findings.append({'code': 'AUTHORITY_CHANGED', 'path': name})
    checked, absent = 0, []
    for name, accepted in sorted(by_path.items()):
        path = repo / name
        if any(parent.is_symlink() for parent in path.parents if parent != repo and parent.is_relative_to(repo)):
            findings.append({'code': 'AUTHORITY_PATH_UNSAFE', 'path': name})
            continue
        if not path.exists() and not path.is_symlink():
            tracked = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'HEAD:{name}'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if tracked:
                findings.append({'code': 'AUTHORITY_MISSING', 'path': name})
            else:
                absent.append(name)
            continue
        # #306 A1 pins a Git symlink blob, not the bytes of its target.
        raw = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        actual = digest(raw)
        checked += 1
        if actual not in accepted:
            findings.append({'code': 'AUTHORITY_DRIFT', 'path': name, 'actual_sha256': actual,
                             'expected_sha256': sorted(accepted)})
    return {'findings': findings, 'checked_files': checked, 'registered_but_absent': absent,
            'allowed_changes': sorted(changed & by_path.keys() & set(allowed))}


def signature(kind, value):
    return digest((kind + '\0' + value).encode())


def python_imports(tree, name):
    package = list(PurePosixPath(name).parts[1:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            parts = package[:len(package) - node.level + 1] if node.level else []
            if node.module:
                parts += node.module.split('.')
            module = '.'.join(parts)
            yield node.lineno, module
            for alias in node.names:
                yield node.lineno, module + '.' + alias.name
        elif isinstance(node, ast.Call) and node.args:
            function = node.func
            dynamic = ((isinstance(function, ast.Name) and function.id == '__import__')
                       or (isinstance(function, ast.Attribute) and function.attr == 'import_module'))
            if dynamic and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                yield node.lineno, node.args[0].value


def inference_hits(repo, rules):
    pattern = re.compile(rules['forbidden_string_pattern'])
    prefixes = rules['forbidden_import_prefixes']
    if not isinstance(prefixes, list) or not prefixes or not all(isinstance(p, str) and p for p in prefixes):
        raise ValueError('forbidden imports missing')
    hits, scanned = [], 0

    def add(name, line, kind, value, code):
        hits.append({'path': name, 'line': line, 'kind': kind, 'sha256': signature(kind, value), 'code': code})

    roots = list(rules['python_roots']) + list(rules['javascript_roots'])
    for name, path in source_files(repo, roots, {'.py', '.mjs'}):
        if path.is_symlink():
            hits.append({'path': name, 'code': 'INFERENCE_SYMLINK'})
            continue
        scanned += 1
        try:
            source = path.read_text(encoding='utf-8')
            if path.suffix == '.py':
                tree = ast.parse(source, filename=name)
                # A single import can yield both its module and member; retain one per exact module.
                seen = set()
                for line, module in python_imports(tree, name):
                    if (line, module) not in seen and any(module.startswith(p) for p in prefixes):
                        add(name, line, 'python_import', module, 'FORBIDDEN_IMPORT')
                        seen.add((line, module))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and pattern.search(node.value):
                        add(name, node.lineno, 'python_string', node.value, 'FORBIDDEN_STRING')
            else:
                for line, text in enumerate(source.splitlines(), 1):
                    if pattern.search(text):
                        add(name, line, 'javascript_line', text.strip(), 'FORBIDDEN_STRING')
        except (SyntaxError, UnicodeError) as exc:
            hits.append({'path': name, 'line': getattr(exc, 'lineno', None), 'code': 'INFERENCE_PARSE_ERROR'})
    return hits, scanned


def inference_check(repo, rules):
    if not rules.get('baseline_ref'):
        raise ValueError('baseline ref missing')
    allowances = Counter()
    exceptions = rules.get('exceptions', [])
    if not isinstance(exceptions, list):
        raise ValueError('invalid inference exceptions')
    for item in exceptions:
        if not isinstance(item.get('issue_ref'), str) or not ISSUE.fullmatch(item['issue_ref']):
            raise ValueError('exception source issue missing')
    for item in rules['baseline'] + exceptions:
        name = relative(item['path'])
        if (item['kind'] not in {'python_string', 'python_import', 'javascript_line'}
                or not SHA.fullmatch(item['sha256']) or type(item['count']) is not int
                or item['count'] < 1 or not item.get('reason')):
            raise ValueError('invalid baseline exception')
        key = (name, item['kind'], item['sha256'])
        if key in allowances:
            raise ValueError('duplicate baseline exception')
        allowances[key] = item['count']
    hits, scanned = inference_hits(repo, rules)
    observed, findings, recognized = Counter(), [], 0
    for hit in hits:
        key = (hit['path'], hit.get('kind'), hit.get('sha256'))
        observed[key] += 1
        if hit.get('sha256') and observed[key] <= allowances[key]:
            recognized += 1
        else:
            findings.append(hit)
    return {'findings': findings, 'scanned_files': scanned, 'recognized_baseline_occurrences': recognized,
            'baseline_ref': rules['baseline_ref']}


def schema_literals(repo):
    literals, errors = [], []
    for name, path in source_files(repo, SCHEMA_ROOTS, TEXT_SUFFIXES):
        if path.is_symlink():
            errors.append({'code': 'SCHEMA_SOURCE_SYMLINK', 'path': name})
            continue
        try:
            source = path.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append({'code': 'SCHEMA_SOURCE_ENCODING', 'path': name})
            continue
        for match in SCHEMA_LITERAL.finditer(source):
            literals.append({'value': match.group(1), 'path': name,
                             'line': source.count('\n', 0, match.start()) + 1})
    return literals, errors


def schemas_check(repo, registry):
    values, findings = set(), []
    for item in registry['schemas']:
        value = item.get('value')
        paths = item.get('source_paths')
        if (not isinstance(value, str) or not value or value in values or not isinstance(paths, list)
                or not paths or not all(isinstance(p, str) for p in paths)
                or not isinstance(item.get('issue_ref'), str) or not ISSUE.fullmatch(item['issue_ref'])):
            findings.append({'code': 'REGISTRY_ENTRY_INVALID', 'value': value})
            continue
        for path in paths:
            relative(path)
        values.add(value)
    literals, errors = schema_literals(repo)
    findings += errors
    findings += [{'code': 'SCHEMA_UNREGISTERED', **item} for item in literals if item['value'] not in values]
    return {'findings': findings, 'registered_values': len(values), 'literal_occurrences': len(literals),
            'registration_is_approval': False}


def check(repo, base, config_dir, allowed=()):
    repo = Path(repo).resolve()
    config_dir = Path(config_dir).resolve()
    try:
        if Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != repo:
            raise ValueError('repo must be a Git checkout root')
        head = git(repo, 'rev-parse', 'HEAD').decode().strip()
        merge_base = git(repo, 'merge-base', base, 'HEAD').decode().strip()
        changed = {os.fsdecode(name) for name in git(repo, 'diff', '--no-renames', '--name-only', '-z', merge_base, 'HEAD').split(b'\0') if name}
        authority = load(config_dir / 'authority_pins_v1.json')
        registry = load(config_dir / 'schema_registry_v1.json')
        rules = load(config_dir / 'inference_import_rules_v1.json')
        checks = {
            'authority': authority_check(repo, changed, authority, [relative(name) for name in allowed]),
            'inference': inference_check(repo, rules),
            'schemas': schemas_check(repo, registry),
        }
        for result in checks.values():
            result['status'] = 'FAIL' if result['findings'] else 'PASS'
        return {'status': 'FAIL' if any(r['findings'] for r in checks.values()) else 'PASS',
                'base': base, 'merge_base': merge_base, 'head': head, 'checks': checks}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error, subprocess.CalledProcessError) as exc:
        return {'status': 'FAIL', 'base': base, 'checks': {},
                'errors': [{'code': 'POLICY_OR_REPOSITORY_INVALID', 'error_type': type(exc).__name__}]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--base', default='origin/codex/q1q5-staging')
    parser.add_argument('--config-dir', type=Path)
    parser.add_argument('--allow', action='append', default=[], metavar='REPOSITORY_PATH',
                        help='Allow a changed authority path only; still require a #306 recognized bytes pin.')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    result = check(args.repo, args.base, args.config_dir or args.repo / 'configs/architecture', args.allow)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if args.report:
        args.report.write_text(raw, encoding='utf-8')
    print(raw, end='')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
