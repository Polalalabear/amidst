"""Shared -T helpers for DEMO_UI_SUPPORT_V1 (contract §2–§5); not collected by pytest."""
import importlib
import importlib.util
import os

import pytest


def strict():
    return os.environ.get('AMIDST_REQUIRE_IMPL') == '1'


def missing(code):
    if strict():
        pytest.fail(code)
    pytest.skip(code)


def require_module(env_name, default, code, attrs=()):
    name = os.environ.get(env_name, default)
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        missing(code)
    module = importlib.import_module(name)
    for attr in attrs:
        if not hasattr(module, attr):
            missing(code)
    return module


def require_route(route, code):
    from amidst.q1q5 import api
    if route not in api.POST_ROUTES:
        missing(code)
    return api


def require_api_attr(attr, code):
    from amidst.q1q5 import api
    if not hasattr(api, attr):
        missing(code)
    return api


FORBIDDEN_TOKENS = ('ground_truth', 'gt_', 'actor', 'renderer_trajectory', 'trajectory', 'visibility',
                    'depth', 'event_script', 'persons.sim', 'private_evaluation')


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)
