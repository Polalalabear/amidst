"""Same Workbench Q session and real RGB pin checks using synthetic test controls."""

import json
from pathlib import Path

import pytest
from test_linked_runtime import inputs, pin

from amidst.q1q5.linked_workbench import MEDIA, application


def app(tmp_path, monkeypatch):
    rgb, prepared = inputs(tmp_path)
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY", str(prepared / "registry.json"))
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY_SHA256", pin(prepared / "registry.json"))
    monkeypatch.delenv("AMIDST_Q1Q5_OLLAMA_RUNTIME", raising=False)
    monkeypatch.delenv("AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256", raising=False)
    return application(
        Path(__file__).resolve().parents[2],
        rgb / "rgb.json",
        pin(rgb / "rgb.json"),
        tmp_path / "private",
    ), rgb


def frames(a, token):
    return a.q_api.call(
        "q_frames",
        dict(
            session_ref=token,
            scene_id="SYNTHETIC_SCENE",
            run_id="SYNTHETIC_RUN",
            timestamp_us=0,
            camera_ids=["A", "B"],
        ),
        lambda token, scene, **kw: a.workbench._session(token),
    )


def media(a, url, **changes):
    path, query = url.split("?")
    env = dict(
        PATH_INFO=path,
        QUERY_STRING=query,
        REQUEST_METHOD="GET",
        HTTP_HOST="127.0.0.1:8765",
        SERVER_PORT="8765",
        **changes,
    )
    return a._dispatch(env)


def test_session_scene_png_and_recording_store_share_application(tmp_path, monkeypatch):
    a, rgb = app(tmp_path, monkeypatch)
    token = a.workbench.session(dict(role="research"))["session_ref"]
    result = frames(a, token)
    assert result["data_origin"] == "SYNTHETIC" and result["provenance"]["gt_read"] is False
    assert (
        media(a, result["tiles"][0]["media_url"]).body == (rgb / "media/camera-A.png").read_bytes()
    )
    assert a.q_api.recording_store.root == tmp_path / "private/recordings"


@pytest.mark.parametrize("change", ["origin", "expired", "session", "tamper", "host"])
def test_media_rejects_origin_expiry_revoked_session_tamper_and_host(tmp_path, monkeypatch, change):
    a, rgb = app(tmp_path, monkeypatch)
    token = a.workbench.session(dict(role="research"))["session_ref"]
    url = frames(a, token)["tiles"][0]["media_url"]
    kwargs = {}
    if change == "origin":
        kwargs["HTTP_ORIGIN"] = "https://invalid.example"
    elif change == "expired":
        a.q_api.rgb_api.clock = lambda: float("inf")
    elif change == "session":
        a.workbench.sessions.clear()
    elif change == "host":
        response = a._dispatch(
            dict(
                PATH_INFO=MEDIA,
                QUERY_STRING=url.split("?")[1],
                REQUEST_METHOD="GET",
                HTTP_HOST="remote.example:8765",
                SERVER_PORT="8765",
            )
        )
        assert response.status == 403
        return
    else:
        (rgb / "media/camera-A.png").write_bytes(b"tampered")
    assert media(a, url, **kwargs).status == 403


def test_no_token_public_path_or_cross_scene_grant(tmp_path, monkeypatch):
    a, _ = app(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        frames(a, "missing")
    assert media(a, MEDIA + "?token=missing").status == 403
    assert (
        json.loads(media(a, MEDIA + "?token=missing").body)["error_code"] == "RGB_ACCESS_REJECTED"
    )
