"""Stdlib-only validator for the JSON Schema subset used by the ``q-demo`` contract schemas.

Only the keywords listed in ``_VALIDATING`` are interpreted; any other non-annotation keyword makes
the schema itself invalid, so a typo can never become a silent no-op. Integers reject ``bool`` and
floats (microsecond fields are integers in the contract).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_ANNOTATIONS = {
    "$schema",
    "$id",
    "$comment",
    "title",
    "description",
    "examples",
    "default",
    "x-contract-ref",
    "x-contract-status",
}
_VALIDATING = {
    "type",
    "enum",
    "const",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "pattern",
    "oneOf",
    "anyOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "$ref",
    "$defs",
}


@dataclass(frozen=True)
class SchemaError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class SchemaDefinitionError(ValueError):
    """The schema itself uses an unsupported keyword or an unresolved ``$ref``."""


Loader = Callable[[str], dict[str, Any]]


def _is_type(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    raise SchemaDefinitionError(f"unknown type {name!r}")


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return {str: "string", list: "array", dict: "object"}.get(type(value), type(value).__name__)


class Validator:
    """Validate an instance against a schema; ``loader`` resolves ``file#/pointer`` refs."""

    def __init__(self, loader: Loader) -> None:
        self._loader = loader

    def validate(self, instance: Any, schema_name: str) -> list[SchemaError]:
        root = self._loader(schema_name)
        errors: list[SchemaError] = []
        self._walk(instance, root, root, schema_name, "$", errors)
        return errors

    # ------------------------------------------------------------------ internals

    def _resolve(self, ref: str, root: dict[str, Any], root_name: str) -> tuple[dict, dict, str]:
        file_part, _, pointer = ref.partition("#")
        if file_part:
            target_name = file_part
            target_root = self._loader(file_part)
        else:
            target_name, target_root = root_name, root
        node: Any = target_root
        for token in [t for t in pointer.split("/") if t]:
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or token not in node:
                raise SchemaDefinitionError(f"unresolved $ref {ref!r}")
            node = node[token]
        return node, target_root, target_name

    def _walk(
        self,
        value: Any,
        schema: dict[str, Any],
        root: dict[str, Any],
        root_name: str,
        path: str,
        errors: list[SchemaError],
    ) -> None:
        unknown = set(schema) - _ANNOTATIONS - _VALIDATING
        if unknown:
            raise SchemaDefinitionError(f"unsupported keyword(s) {sorted(unknown)} at {path}")
        if "$ref" in schema:
            node, new_root, new_name = self._resolve(schema["$ref"], root, root_name)
            self._walk(value, node, new_root, new_name, path, errors)
        if "type" in schema:
            wanted = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is_type(value, t) for t in wanted):
                errors.append(
                    SchemaError(path, f"expected type {'|'.join(wanted)}, got {_type_name(value)}")
                )
                return
        if "const" in schema and (
            value != schema["const"] or _type_name(value) != _type_name(schema["const"])
        ):
            errors.append(SchemaError(path, f"must equal {schema['const']!r}, got {value!r}"))
        if "enum" in schema and not any(
            value == option and _type_name(value) == _type_name(option) for option in schema["enum"]
        ):
            errors.append(SchemaError(path, f"{value!r} not in closed list {schema['enum']!r}"))
        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append(SchemaError(path, f"string shorter than {schema['minLength']}"))
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                errors.append(SchemaError(path, f"{value!r} does not match {schema['pattern']!r}"))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(SchemaError(path, f"{value!r} < minimum {schema['minimum']!r}"))
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(SchemaError(path, f"{value!r} > maximum {schema['maximum']!r}"))
            if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
                errors.append(
                    SchemaError(
                        path, f"{value!r} <= exclusiveMinimum {schema['exclusiveMinimum']!r}"
                    )
                )
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append(SchemaError(path, f"fewer than {schema['minItems']} items"))
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                errors.append(SchemaError(path, f"more than {schema['maxItems']} items"))
            if "items" in schema:
                for index, item in enumerate(value):
                    self._walk(item, schema["items"], root, root_name, f"{path}[{index}]", errors)
        if isinstance(value, dict):
            props = schema.get("properties", {})
            for name in schema.get("required", []):
                if name not in value:
                    errors.append(SchemaError(path, f"missing required key {name!r}"))
            for name, item in value.items():
                child = f"{path}.{name}"
                if name in props:
                    self._walk(item, props[name], root, root_name, child, errors)
                elif schema.get("additionalProperties", True) is False:
                    errors.append(SchemaError(child, "additional property not allowed"))
                elif isinstance(schema.get("additionalProperties"), dict):
                    self._walk(item, schema["additionalProperties"], root, root_name, child, errors)
        self._combinators(value, schema, root, root_name, path, errors)

    def _branch_errors(
        self, value: Any, branch: dict[str, Any], root: dict, root_name: str, path: str
    ) -> list[SchemaError]:
        found: list[SchemaError] = []
        self._walk(value, branch, root, root_name, path, found)
        return found

    def _combinators(
        self,
        value: Any,
        schema: dict[str, Any],
        root: dict[str, Any],
        root_name: str,
        path: str,
        errors: list[SchemaError],
    ) -> None:
        for branch in schema.get("allOf", []):
            self._walk(value, branch, root, root_name, path, errors)
        for keyword in ("anyOf", "oneOf"):
            if keyword not in schema:
                continue
            results = [
                self._branch_errors(value, b, root, root_name, path) for b in schema[keyword]
            ]
            matched = sum(1 for r in results if not r)
            ok = matched >= 1 if keyword == "anyOf" else matched == 1
            if not ok:
                best = min(results, key=len)
                detail = "; ".join(str(e) for e in best[:3])
                reason = (
                    "no alternative matched" if matched == 0 else "several alternatives matched"
                )
                errors.append(SchemaError(path, f"{keyword}: {reason} ({detail})"))
        if "not" in schema and not self._branch_errors(value, schema["not"], root, root_name, path):
            errors.append(SchemaError(path, "matches a forbidden alternative"))
        if "if" in schema:
            if not self._branch_errors(value, schema["if"], root, root_name, path):
                if "then" in schema:
                    self._walk(value, schema["then"], root, root_name, path, errors)
            elif "else" in schema:
                self._walk(value, schema["else"], root, root_name, path, errors)
