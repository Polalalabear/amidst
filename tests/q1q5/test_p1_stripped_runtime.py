"""Synthetic source/served pin and public PNG checks for the P1 adapter."""

import hashlib
import json
import struct
import zlib

import pytest

from amidst.q1q5.p1_workbench import bundle_media_reader, public_png


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def test_public_png_removes_exif_and_text_without_changing_idat():
    header = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    data = chunk(b'IDAT', zlib.compress(b'\x00\x01\x02\x03'))
    end = chunk(b'IEND', b'')
    source = header + chunk(b'tEXt', b'key\x00synthetic') + chunk(b'eXIf', b'synthetic') + data + end
    served = public_png(source)
    assert served == header + data + end
    assert sha(source) != sha(served)


def fixture(root):
    name = 'data/rgb/media/A-0000.png'
    served = b'synthetic served bytes'
    path = root / name
    path.parent.mkdir(parents=True)
    path.write_bytes(served)
    source = {'files': {name: {'sha256': 'a' * 64, 'bytes': 42}}}
    source_raw = json.dumps(source).encode()
    (root / 'SOURCE_MANIFEST.json').write_bytes(source_raw)
    entry = {'original_file_sha256': 'a' * 64, 'file_sha256': sha(served),
             'original_pixel_sha256': 'b' * 64, 'pixel_sha256': 'b' * 64,
             'idat_sha256': 'c' * 64, 'metadata_key_names': []}
    transform = {'format': 'p1-media-transform.v1', 'source_manifest_ref': 'SOURCE_MANIFEST.json',
                 'source_manifest_sha256': sha(source_raw), 'entries': {name: entry}}
    transform_raw = json.dumps(transform).encode()
    (root / 'MEDIA_TRANSFORM.json').write_bytes(transform_raw)
    manifest = {'media_transform_ref': 'MEDIA_TRANSFORM.json', 'files': {
        name: {'sha256': sha(served)},
        'SOURCE_MANIFEST.json': {'sha256': sha(source_raw)},
        'MEDIA_TRANSFORM.json': {'sha256': sha(transform_raw)}}}
    return path, manifest


def test_source_pin_remains_original_and_served_bytes_are_pinned(tmp_path):
    path, manifest = fixture(tmp_path)
    reader = bundle_media_reader(tmp_path, manifest)
    assert reader(path, 'a' * 64) == b'synthetic served bytes'
    with pytest.raises(ValueError, match='MEDIA_TRANSFORM_SOURCE_MISMATCH'):
        reader(path, 'd' * 64)
    path.write_bytes(b'tampered served bytes')
    with pytest.raises(ValueError, match='RGB_PIN_MISMATCH'):
        reader(path, 'a' * 64)


def test_undeclared_png_fails_before_read(tmp_path):
    path, manifest = fixture(tmp_path)
    reader = bundle_media_reader(tmp_path, manifest)
    other = path.with_name('B-0000.png')
    with pytest.raises(ValueError, match='MEDIA_TRANSFORM_SOURCE_MISMATCH'):
        reader(other, 'a' * 64)
