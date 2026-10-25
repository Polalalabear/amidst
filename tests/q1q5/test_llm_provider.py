"""SYNTHETIC provider tests; never call Ollama or load any model."""
import hashlib
import json
from urllib.error import HTTPError, URLError

import pytest

from amidst.q1q5.llm_provider import (
    FakeProvider, FakeTransport, LocalHTTPTransport, OllamaProvider, ProviderError,
)

MODEL = "qwen2.5:7b-instruct"
DIGEST = "a" * 64


def packed(value):
    return json.dumps(value).encode()


def tags(digest=DIGEST):
    return packed({"models": [{"name": MODEL, "digest": digest}]})


def generated(**changes):
    return packed({"model": MODEL, "done": True, "response": '{"intent":"UNSUPPORTED"}',
                   **changes})


def call(provider, **changes):
    args = dict(model=MODEL, prompt="SYNTHETIC: find red person", template="SYNTHETIC:{query}",
                template_version="synthetic-v1", options={"temperature": 0, "seed": 7},
                timeout_ms=2000, expected_digest=DIGEST)
    return provider.generate(**(args | changes))


def test_record_is_reproducible_and_raw_prompt_is_exact():
    p = FakeProvider([tags(), generated(), tags()], clock=lambda: 1.0)
    result = call(p)
    assert result.text == '{"intent":"UNSUPPORTED"}'
    record = result.record
    assert record["model_digest"] == DIGEST
    assert record["validation"] == "PROVIDER_VALIDATED"
    assert record["prompt_sha256"] == hashlib.sha256(record["prompt"].encode()).hexdigest()
    assert record["raw_output_sha256"] == hashlib.sha256(result.text.encode()).hexdigest()
    hash_input = {k: v for k, v in record.items() if k not in ("stats", "content_sha256")}
    assert record["content_sha256"] == hashlib.sha256(json.dumps(
        hash_input, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode()).hexdigest()
    assert [(c[0], c[1]) for c in p.transport.calls] == [
        ("GET", "/api/tags"), ("POST", "/api/generate"), ("GET", "/api/tags")]
    sent = p.transport.calls[1][2]
    assert sent["raw"] is True and sent["stream"] is False
    assert sent["prompt"] == record["prompt"] and "images" not in sent


@pytest.mark.parametrize("response,code", [
    (TimeoutError(), "PROVIDER_TIMEOUT"),
    (URLError(TimeoutError()), "PROVIDER_TIMEOUT"),
    (URLError("connection refused"), "PROVIDER_UNAVAILABLE"),
    (HTTPError("http://localhost", 503, "unavailable", {}, None), "PROVIDER_UNAVAILABLE"),
    (ConnectionError(), "PROVIDER_UNAVAILABLE"),
    (packed({"models": []}), "PROVIDER_UNAVAILABLE"),
    (b"not json", "INVALID_RESPONSE"),
    (packed([]), "INVALID_RESPONSE"),
    (packed({"models": [{"name": MODEL, "digest": "wrong"}]}), "INVALID_RESPONSE"),
    (packed({"models": "bad"}), "INVALID_RESPONSE"),
])
def test_errors_are_classified_recorded_and_never_retried(response, code):
    transport = FakeTransport([response])
    with pytest.raises(ProviderError) as err:
        call(OllamaProvider(transport, clock=lambda: 0))
    assert err.value.code == code
    assert err.value.record["validation_errors"] == [code]
    assert err.value.record["prompt"]
    assert len(transport.calls) == 1
    assert err.value.record["timed_out"] == (code == "PROVIDER_TIMEOUT")


@pytest.mark.parametrize("raw", [
    b'{"done":true,"done":true}', b"\xff", b'{"done":NaN}',
    generated(done=False), generated(model="other"), generated(response=""),
    generated(response=7), generated(error="failure"),
])
def test_invalid_generation_envelopes(raw):
    with pytest.raises(ProviderError) as err:
        call(FakeProvider([tags(), raw]))
    assert err.value.code == "INVALID_RESPONSE"
    assert err.value.record["response_body_sha256"] == hashlib.sha256(raw).hexdigest()


def test_pin_and_tag_mutation_fail_closed():
    for responses in ([tags("b" * 64)], [tags(), generated(), tags("b" * 64)]):
        with pytest.raises(ProviderError) as err:
            call(FakeProvider(responses))
        assert err.value.code == "INVALID_RESPONSE"


def test_deadline_covers_metadata_and_generation():
    ticks = iter([0, 0, .1, .2, 1.9, 2.1, 2.2])
    transport = FakeTransport([tags(), generated()])
    with pytest.raises(ProviderError) as err:
        call(OllamaProvider(transport, clock=lambda: next(ticks)))
    assert err.value.code == "PROVIDER_TIMEOUT"
    assert transport.calls[1][3] == pytest.approx(1.8)


@pytest.mark.parametrize("url", [
    "https://example.com", "http://example.com", "http://192.168.1.2:11434",
    "http://127.0.0.1@evil.test", "http://user@localhost", "http://localhost/other",
    "http://localhost?redirect=evil", "http://localhost/#x", "file:///tmp/model",
])
def test_only_local_http_origins_are_allowed(url):
    with pytest.raises(ValueError):
        LocalHTTPTransport(url)


@pytest.mark.parametrize("url", ["http://localhost:11434", "http://127.0.0.1:11434",
                                 "http://[::1]:11434"])
def test_loopback_origins_and_no_proxy(url):
    transport = LocalHTTPTransport(url)
    assert transport.base_url in ("http://127.0.0.1:11434", "http://[::1]:11434")
    with pytest.raises(ValueError):
        transport.request("POST", "/api/pull", {}, 1)


@pytest.mark.parametrize("changes", [
    {"timeout_ms": 0}, {"timeout_ms": True}, {"prompt": "read /Users/local/secret"},
    {"expected_digest": "invalid"}, {"options": {"seed": float("nan")}},
    {"options": {"num_ctx": "unbounded"}}, {"options": {"seed": True}},
    {"model": "bad model"}, {"template_version": ""},
])
def test_invalid_caller_inputs_do_not_make_requests(changes):
    p = FakeProvider([])
    with pytest.raises(ValueError):
        call(p, **changes)
    assert not p.transport.calls


def test_bounded_transport_and_no_redirects():
    transport = LocalHTTPTransport("http://localhost", max_response_bytes=8)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, size):
            assert size == 9
            return b"x" * 9

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/tags"
            assert timeout == 1
            return Response()

    transport.opener = Opener()
    with pytest.raises(ValueError, match="exceeds"):
        transport.request("GET", "/api/tags", None, 1)
    from amidst.q1q5.llm_provider import _NoRedirect
    assert _NoRedirect().redirect_request(None, None, 302, "", {}, "http://evil") is None
