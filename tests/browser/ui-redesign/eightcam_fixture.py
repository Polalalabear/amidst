"""Owned, ephemeral integration service for the focused 8CAM browser smoke."""

import json
import sys
import tempfile
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from demo_dependency_config import configuration, install_owned_io_guard, owned_path
from demo_eightcam import prepare_eightcam
from serve_demo_integration import Demo, server

config, root = configuration()
eightcam, reason = prepare_eightcam(sys.argv[1])
install_owned_io_guard(root, approved_read_files=eightcam.read_files)
state_root = owned_path(root, config["state_root"])
state = Path(tempfile.mkdtemp(prefix="eightcam-browser-", dir=state_root)) / "state"
app = Demo(
    owned_path(root, config["artifacts_root"]),
    owned_path(root, config["p1_bundle"]),
    state,
    job_path=owned_path(root, config["cross_camera_job"]),
    job_pin=config["cross_camera_job_sha256"],
    owned_root=root,
    eightcam=eightcam,
    eightcam_reason=reason,
)
with server(app, 0) as http:
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        print(json.dumps({"port": http.server_port, "eightcam": app.eightcam_status}), flush=True)
        sys.stdin.readline()
    finally:
        http.shutdown()
        thread.join(timeout=5)
