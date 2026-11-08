"""Synthetic safety checks; no model, media or GT input."""
import hashlib
from pathlib import Path

import pytest

from amidst.q1q5.r005_detection_probe import CAMERAS, safe_bytes, validate_frames


def test_safe_bytes_rejects_tamper_and_symlink(tmp_path):
    p = tmp_path / 'frame.png'
    p.write_bytes(b'synthetic')
    pin = hashlib.sha256(b'synthetic').hexdigest()
    assert safe_bytes(p, pin, 9) == b'synthetic'
    with pytest.raises(ValueError, match='INPUT_PIN_MISMATCH'):
        safe_bytes(p, pin, 8)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError, match='INPUT_PIN_MISMATCH'):
        safe_bytes(p, pin)
    link = tmp_path / 'link.png'
    link.symlink_to(p)
    with pytest.raises(ValueError, match='SYMLINK_INPUT'):
        safe_bytes(link, hashlib.sha256(b'changed').hexdigest())


def test_only_six_static_camera_images_are_returned(tmp_path):
    rows, files = [], {}
    for camera in (*CAMERAS, 'HUMAN_LAYOUT'):
        relative = f'rgb/{camera}.png' if camera in CAMERAS else 'human_layout/overview.png'
        purpose = 'STATIC_CAMERA_RGB' if camera in CAMERAS else 'HUMAN_LAYOUT_ONLY'
        p = tmp_path / relative
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(camera.encode())
        pin = hashlib.sha256(camera.encode()).hexdigest()
        rows.append({'camera_id': camera, 'file': relative, 'purpose': purpose, 'sha256': pin})
        files[relative] = {'sha256': pin, 'bytes': len(camera)}
    receipt = {'scene_id': 'office_expanded_r005', 'preview_revision': 'v2',
               'rendered': rows, 'files': files}
    result = validate_frames(tmp_path, receipt)
    assert [x['camera_id'] for x in result] == list(CAMERAS)
    receipt['rendered'][-1]['purpose'] = 'STATIC_CAMERA_RGB'
    with pytest.raises(ValueError, match='RECEIPT_PURPOSE_MISMATCH'):
        validate_frames(tmp_path, receipt)
