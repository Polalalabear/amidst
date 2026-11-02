"""Register and select CQ-21-T's test-only contract alternatives."""
import json
import os
from pathlib import Path


def pytest_configure(config):
    config.addinivalue_line("markers", "contract_option(group, value): PROPOSED CQ-21a alternative; no production adoption")


def pytest_collection_modifyitems(config, items):
    value = os.environ.get("AMIDST_RECEIPT_CONTRACT")
    if not value:
        return
    try:
        options = json.loads(value if value.lstrip().startswith("{") else Path(value).read_text())
    except (ValueError, OSError):
        return  # The scoped tests report invalid configuration explicitly.
    if not isinstance(options, dict):
        return
    kept, deselected = [], []
    for item in items:
        marker = item.get_closest_marker("contract_option") if item.path.name == "test_g4_receipt_overlay.py" else None
        if marker and options.get(marker.args[0]) not in (None, "UNSELECTED", marker.args[1]):
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        items[:] = kept
        config.hook.pytest_deselected(items=deselected)
