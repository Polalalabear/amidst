"""JSON Schemas for ``docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`` (DRAFT, not an approved contract).

Every ``schema_version`` named in the contract has one file under ``schemas/``. Files whose
``x-contract-status`` is set are *provisional*: the contract names their fields but does not define
a schema, so they are kit conventions awaiting a contract revision.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from amidst.contracts.q_demo.mini_schema import SchemaError, Validator

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# schema_version (or role name for documents without one) -> schema file
SCHEMA_FILES: dict[str, str] = {
    "q-demo.clock-mapping.v1": "clock-mapping.v1.schema.json",
    "q-demo.detection-index.v1": "detection-index.v1.schema.json",
    "q-demo.detection-record": "detection-record.schema.json",
    "q-demo.region-graph.v1": "region-graph.v1.schema.json",
    "q-demo.camera-transition-graph.v1": "camera-transition-graph.v1.schema.json",
    "q-demo.q1-request.v1": "q1-request.v1.schema.json",
    "q-demo.q1-response.v1": "q1-response.v1.schema.json",
    "q-demo.q3-parse-request.v1": "q3-parse-request.v1.schema.json",
    "q-demo.q3-llm-output.v1": "q3-llm-output.v1.schema.json",
    "q-demo.q3-parse-response.v1": "q3-parse-response.v1.schema.json",
    "q-demo.explanation.v1": "explanation.v1.schema.json",
    "q-demo.q2-request.v1": "q2-request.v1.schema.json",
    "q-demo.q2-response.v1": "q2-response.v1.schema.json",
    "q-demo.agent-decision.v1": "agent-decision.v1.schema.json",
    "q-demo.decision-record.v1": "decision-record.v1.schema.json",
    "q-demo.candidate-snapshot.v1": "candidate-snapshot.v1.schema.json",
    "q-demo.candidate-evidence.v1": "candidate-evidence.v1.schema.json",
    "q-demo.parameter-set.v1": "parameter-set.v1.schema.json",
    "q-demo.link-record.v1": "link-record.v1.schema.json",
    "q-demo.link-record.v2": "link-record.v2.schema.json",
    "q1q5-conformance.supported-classes.v1": "kit-supported-classes.v1.schema.json",
    "q-demo.supported-classes.v1": "kit-supported-classes.v1.schema.json",
}


@cache
def load_schema(file_name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / file_name).read_text(encoding="utf-8"))


_VALIDATOR = Validator(load_schema)


def validate(instance: Any, schema_key: str) -> list[SchemaError]:
    """Validate ``instance`` against the schema registered under ``schema_key``."""

    return _VALIDATOR.validate(instance, SCHEMA_FILES[schema_key])


def is_provisional(schema_key: str) -> bool:
    return "x-contract-status" in load_schema(SCHEMA_FILES[schema_key])


__all__ = ["SCHEMA_DIR", "SCHEMA_FILES", "SchemaError", "is_provisional", "load_schema", "validate"]
