"""Pinned replay launcher, with no model or outbound-network startup calls."""
import errno
from pathlib import Path
import shutil
import sys

from amidst.q1q5.api import UNAVAILABLE_POST_ROUTES, APIError
from amidst.q1q5.p1_workbench import P1, server


class LauncherError(ValueError):
    pass


class RecordedAPI:
    """Keep the run metadata needed to play RGB; reject new inference requests."""
    READ_ONLY = frozenset({'q_recorded_response', 'q2_artifact', 'q_media_grant', 'q_frames', 'q_candidate_view'})

    def __init__(self, api):
        self.api = api

    def __getattr__(self, name):
        return getattr(self.api, name)

    def bootstrap(self):
        result = self.api.bootstrap()
        result['data_origin'] = 'RECORDED'
        return result

    def call(self, action, payload, authorize):
        # These paths only report unavailable after authorization; no inference
        # or UI-support implementation is enabled in recorded mode.
        if action not in self.READ_ONLY | UNAVAILABLE_POST_ROUTES:
            raise APIError('RECORDED_READ_ONLY', 409)
        return self.api.call(action, payload, authorize)


def prepare_demo(bundle, manifest_sha256, state_root, *, live=False, ui_root=None, app_factory=None):
    if sys.version_info < (3, 12):
        raise LauncherError('PYTHON_3_12_REQUIRED')
    bundle, state_root = Path(bundle), Path(state_root)
    if (bundle.resolve() != bundle or state_root.resolve() != state_root
            or not state_root.parent.is_dir() or state_root.exists()
            or state_root.is_relative_to(bundle)):
        raise LauncherError('NEW_CANONICAL_STATE_OUTSIDE_BUNDLE_REQUIRED')
    if shutil.disk_usage(state_root.parent).free < 8 * 1024**3:
        raise LauncherError('DISK_BELOW_8_GIB')
    # No runtime is selected for this bounded replay delivery. P1 also clears
    # inherited Ollama runtime settings before building the read-only QAPI.
    app = (app_factory or P1)(bundle, manifest_sha256, state_root, ui_root=ui_root)
    selected = app.spec.get('default_recording_id')
    if selected not in app.api.recordings:
        raise LauncherError('PINNED_DEFAULT_RECORDING_REQUIRED')
    app.api = RecordedAPI(app.api)
    return app, {'mode': 'RECORDED', 'recording_id': selected,
                 'fallback_reason': 'LIVE_RUNTIME_NOT_SELECTED' if live else None,
                 'source_commit': app.manifest['source_commit'], 'manifest_sha256': manifest_sha256,
                 'live_requested': live, 'model_calls': 0, 'gt_read': False}


def bind_demo(app, port=0):
    if type(port) is not int or not 0 <= port <= 65535:
        raise LauncherError('INVALID_LOOPBACK_PORT')
    try:
        return server(app, port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise LauncherError('PORT_IN_USE') from None
        raise
