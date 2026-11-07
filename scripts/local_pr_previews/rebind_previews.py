"""Reproduce locator/health edits once, on already copied and pinned previews.

This copies no payload, opens no original RGB, and refuses unexpected bytes.
The caller must first create the user's authorized, byte-verified LOCAL copies.
"""
from pathlib import Path
import argparse
import hashlib
import json


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def rebind(root):
    root = Path(root).absolute()
    if root.resolve() != root or root.is_symlink():
        raise ValueError('CANONICAL_COPY_ROOT_REQUIRED')
    def core(text):
        old = 'source_head:head,route_calls:'
        if text.count(old) != 1:
            raise ValueError('CORE_PATCH_SOURCE')
        return text.replace(old, 'source_head:head,source_checkout:root,route_calls:')
    def viewer(text):
        old = "const repo='/private/tmp/amidst-d128-427';"
        if text.count(old) != 1:
            raise ValueError('VIEWER_PATCH_SOURCE')
        return text.replace(old, 'const repo=' + json.dumps(str(root/'checkouts/pr442')) + ';').replace(
            'JSON.stringify({head,source_manifest_sha256:',
            'JSON.stringify({head,source_checkout:repo,source_manifest_sha256:')
    def review(text):
        old = '    return routes\n'
        if text.count(old) != 1:
            raise ValueError('REVIEW_PATCH_SOURCE')
        return text.replace(old, "    routes['/__preview/health'] = (json.dumps({'report_sha256': data['report_sha256'], 'source_directory': str(HERE)}).encode(), 'application/json; charset=utf-8')\n    return routes\n")
    def locator(text):
        doc = json.loads(text)
        doc['screenshots_directory'] = str(root/'r005-review/screenshots')
        doc['prior_manifest_sha256'] = '826fa8999c14964e9766241e1f13876be6bc63c528dc60093b6268935a0ee88f'
        return json.dumps(doc, indent=2) + '\n'
    recipes = [
        ('tooling/preview-server.mjs', '9026846ac86e1ee809f7d3ce58c4b29a86f4589f754e979cd51e5f1a78ea543f', core),
        ('d124-viewer/server.mjs', 'de74c728eaf7afb0303ebc6f8a8a212e9083bdbc0329328fb50edaedd6d64a0c', viewer),
        ('r005-review/server.py', 'eda4d1eaa1b0215d61b3cb96c0eeac23a9b754c966f3dbd6a298f64c92b56669', review),
        ('r005-review/manifest.json', '826fa8999c14964e9766241e1f13876be6bc63c528dc60093b6268935a0ee88f', locator),
    ]
    changes = []
    for name, pin, transform in recipes:
        path = root/name
        if path.resolve() != path or path.is_symlink():
            raise ValueError('CANONICAL_COPIED_FILE_REQUIRED')
        raw = path.read_bytes()
        if digest(raw) != pin:
            raise ValueError('ORIGINAL_COPY_PIN_REQUIRED:' + name)
        changes.append((path, pin, transform(raw.decode()).encode()))
    for path, old, raw in changes:
        path.write_bytes(raw)
    return [{'path': str(path), 'original_sha256': old, 'sha256': digest(raw)} for path, old, raw in changes]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    print(json.dumps(rebind(parser.parse_args().root), indent=2))
