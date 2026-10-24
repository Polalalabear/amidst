"""A synchronous session stays active until its immutable response is published."""

import threading

import pytest
from test_api import api_fixture, selected

from amidst.q1q5.api import APIError


def test_duplicate_request_during_publication_cannot_execute_again():
    api, run = api_fixture(agent=True)
    entered, release = threading.Event(), threading.Event()
    original_controller, original_bundle = api._controller, api._bundle
    executions = []

    def controller(*args, **kwargs):
        value = original_controller(*args, **kwargs)
        execute = value.run

        def counted():
            executions.append(value.session_id)
            return execute()

        value.run = counted
        return value

    def bundle(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original_bundle(*args, **kwargs)

    api._controller, api._bundle = controller, bundle
    answers, errors = [], []

    def execute():
        try:
            answers.append(selected(api, run))
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=execute)
    thread.start()
    try:
        assert entered.wait(5)
        assert len(api._active) == 1
        with pytest.raises(APIError) as denied:
            selected(api, run)
        assert denied.value.code == "Q_SESSION_RUNNING"
        assert executions and len(executions) == 1
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors and len(answers) == 1
    assert not api._active
    assert selected(api, run) == answers[0] and len(executions) == 1


@pytest.mark.parametrize("phase", ["bundle", "save"])
def test_publication_failure_cleans_active_and_allows_honest_retry(phase):
    api, run = api_fixture()
    method = "_bundle" if phase == "bundle" else "_save_response"
    original = getattr(api, method)

    def fail(*args, **kwargs):
        raise RuntimeError("SYNTHETIC publication failure")

    setattr(api, method, fail)
    with pytest.raises(RuntimeError):
        selected(api, run)
    assert not api._active and not api.responses
    setattr(api, method, original)
    assert selected(api, run)["status"] == "COMPLETE"
    assert not api._active and len(api.responses) == 1
