"""Minimal JSON Schema (draft 2020-12 subset) validator for the published schemas in ``backend/schemas``.

The core stays stdlib-only, so this implements exactly the keywords the schemas use:
``type`` (incl. lists and ``null``), ``enum``, ``const``, ``properties``, ``required``,
``additionalProperties``, ``patternProperties``, ``propertyNames``, ``items``, ``minItems``,
``maxItems``, ``minLength``, ``maxLength``, ``pattern``, ``minimum``, ``maximum``,
``exclusiveMinimum``, ``exclusiveMaximum``, ``allOf``, ``anyOf``, ``oneOf``, ``if``/``then``/``else``,
``$ref`` (same file ``#/$defs/x`` or another schema file ``other.schema.json#/$defs/x``) and ``$defs``.
Unknown keywords are rejected when a schema file is loaded, so a schema can never silently
rely on something this validator ignores. Any standard validator gives the same answers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"

KNOWN = {
    "$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "examples", "default",
    "type", "enum", "const", "properties", "required", "additionalProperties", "patternProperties",
    "propertyNames", "items", "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum",
    "maximum", "exclusiveMinimum", "exclusiveMaximum", "allOf", "anyOf", "oneOf", "if", "then", "else",
}  # fmt: skip
SUBSCHEMA_MAPS = ("$defs", "properties", "patternProperties")
SUBSCHEMA_LISTS = ("allOf", "anyOf", "oneOf")
SUBSCHEMA_ONE = ("additionalProperties", "propertyNames", "items", "if", "then", "else")


class SchemaError(ValueError):
    pass


def _type_ok(value, t: str) -> bool:
    if t == "null":
        return value is None
    if t == "boolean":
        return isinstance(value, bool)
    if t == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t == "array":
        return isinstance(value, list)
    if t == "object":
        return isinstance(value, dict)
    raise SchemaError(f"unknown type {t!r}")


class Registry:
    """All schema files of a directory, addressed by file name (their ``$id``)."""

    def __init__(self, directory: Path | str = SCHEMA_DIR):
        self.dir = Path(directory)
        self.docs: dict = {}
        for path in sorted(self.dir.glob("*.schema.json")):
            doc = json.loads(path.read_text())
            if doc.get("$id") != path.name:
                raise SchemaError(f"{path.name}: $id must equal the file name")
            self._check_keywords(doc, path.name)
            self.docs[path.name] = doc

    def _check_keywords(self, schema, where: str) -> None:
        if isinstance(schema, bool):
            return
        if not isinstance(schema, dict):
            raise SchemaError(f"{where}: schema must be an object")
        unknown = set(schema) - KNOWN
        if unknown:
            raise SchemaError(f"{where}: unsupported keywords {sorted(unknown)}")
        for key in SUBSCHEMA_MAPS:
            for name, sub in schema.get(key, {}).items():
                self._check_keywords(sub, f"{where}/{key}/{name}")
        for key in SUBSCHEMA_LISTS:
            for i, sub in enumerate(schema.get(key, [])):
                self._check_keywords(sub, f"{where}/{key}/{i}")
        for key in SUBSCHEMA_ONE:
            if key in schema:
                self._check_keywords(schema[key], f"{where}/{key}")

    def resolve(self, ref: str, base: str) -> tuple:
        file, _, pointer = ref.partition("#")
        file = file or base
        if file not in self.docs:
            raise SchemaError(f"unknown schema file in $ref {ref!r}")
        node = self.docs[file]
        for part in [p for p in pointer.split("/") if p]:
            node = node[part]
        return node, file

    def errors(self, instance, schema_file: str, pointer: str = "") -> list:
        """All validation errors as 'path: message' strings (empty list = valid)."""
        schema, base = self.resolve(f"{schema_file}#{pointer}", schema_file)
        out: list = []
        self._validate(instance, schema, base, "$", out)
        return out

    def validate(self, instance, schema_file: str, pointer: str = "") -> None:
        errs = self.errors(instance, schema_file, pointer)
        if errs:
            raise SchemaError("; ".join(errs[:5]))

    # ------------------------------------------------------------------ core
    def _validate(self, v, s, base: str, path: str, out: list) -> None:  # noqa: C901 - one keyword per branch
        if s is True:
            return
        if s is False:
            out.append(f"{path}: not allowed")
            return
        if "$ref" in s:
            target, tbase = self.resolve(s["$ref"], base)
            self._validate(v, target, tbase, path, out)
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_type_ok(v, t) for t in types):
                out.append(f"{path}: expected {'/'.join(types)}")
                return
        if "const" in s and v != s["const"]:
            out.append(f"{path}: must be {s['const']!r}")
        if "enum" in s and v not in s["enum"]:
            out.append(f"{path}: not one of {s['enum']}")
        if isinstance(v, str):
            if "minLength" in s and len(v) < s["minLength"]:
                out.append(f"{path}: shorter than {s['minLength']}")
            if "maxLength" in s and len(v) > s["maxLength"]:
                out.append(f"{path}: longer than {s['maxLength']}")
            if "pattern" in s and not re.search(s["pattern"], v):
                out.append(f"{path}: does not match {s['pattern']}")
        if _type_ok(v, "number"):
            if "minimum" in s and v < s["minimum"]:
                out.append(f"{path}: below {s['minimum']}")
            if "maximum" in s and v > s["maximum"]:
                out.append(f"{path}: above {s['maximum']}")
            if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
                out.append(f"{path}: not above {s['exclusiveMinimum']}")
            if "exclusiveMaximum" in s and v >= s["exclusiveMaximum"]:
                out.append(f"{path}: not below {s['exclusiveMaximum']}")
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                out.append(f"{path}: fewer than {s['minItems']} items")
            if "maxItems" in s and len(v) > s["maxItems"]:
                out.append(f"{path}: more than {s['maxItems']} items")
            if "items" in s:
                for i, item in enumerate(v):
                    self._validate(item, s["items"], base, f"{path}[{i}]", out)
        if isinstance(v, dict):
            for key in s.get("required", []):
                if key not in v:
                    out.append(f"{path}: missing {key!r}")
            props = s.get("properties", {})
            pats = s.get("patternProperties", {})
            for key, item in v.items():
                matched = False
                if key in props:
                    matched = True
                    self._validate(item, props[key], base, f"{path}.{key}", out)
                for pat, sub in pats.items():
                    if re.search(pat, key):
                        matched = True
                        self._validate(item, sub, base, f"{path}.{key}", out)
                if not matched and "additionalProperties" in s:
                    self._validate(item, s["additionalProperties"], base, f"{path}.{key}", out)
                if "propertyNames" in s:
                    self._validate(key, s["propertyNames"], base, f"{path}.<key {key}>", out)
        for sub in s.get("allOf", []):
            self._validate(v, sub, base, path, out)
        if "anyOf" in s and not any(self._ok(v, sub, base) for sub in s["anyOf"]):
            out.append(f"{path}: matches none of anyOf")
        if "oneOf" in s:
            n = sum(self._ok(v, sub, base) for sub in s["oneOf"])
            if n != 1:
                out.append(f"{path}: matches {n} of oneOf (exactly 1 required)")
        if "if" in s:
            branch = s.get("then") if self._ok(v, s["if"], base) else s.get("else")
            if branch is not None:
                self._validate(v, branch, base, path, out)

    def _ok(self, v, s, base: str) -> bool:
        errs: list = []
        self._validate(v, s, base, "$", errs)
        return not errs
