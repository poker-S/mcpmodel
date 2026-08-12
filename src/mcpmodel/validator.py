"""JSON/JSONL loading and schema validation without executing sample content."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMA_FILES = {
    "case": "case.schema.json",
    "authorization": "authorization.schema.json",
    "audit_event": "audit_event.schema.json",
    "source_record": "source_record.schema.json",
    "derived_record": "derived_record.schema.json",
    "authorization_draft": "authorization_draft.schema.json",
    "reconstructed_authorization": "reconstructed_authorization.schema.json",
}


class ValidationFailure(ValueError):
    """Raised when an input document does not conform to the project schema."""


def _schema_dir(schema_dir: Path | None = None) -> Path:
    if schema_dir is not None:
        return schema_dir
    return Path(__file__).resolve().parents[2] / "schemas"


def load_validator(
    schema_name: str = "case", schema_dir: Path | None = None
) -> Draft202012Validator:
    """Build a validator with all local schemas registered by their canonical IDs."""
    if schema_name not in SCHEMA_FILES:
        raise KeyError(f"unknown schema: {schema_name}")

    directory = _schema_dir(schema_dir)
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
    registry = Registry()
    for schema in schemas:
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))

    root = next(schema for schema in schemas if schema["$id"].endswith(SCHEMA_FILES[schema_name]))
    return Draft202012Validator(root, registry=registry, format_checker=FormatChecker())


def validate_document(document: dict[str, Any], schema_name: str = "case") -> None:
    """Validate one object and raise a compact, deterministic error on failure."""
    errors = sorted(
        load_validator(schema_name).iter_errors(document), key=lambda error: list(error.path)
    )
    if not errors:
        return
    rendered = []
    for error in errors:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    raise ValidationFailure("; ".join(rendered))


def iter_documents(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield JSON objects from a .json or line-delimited .jsonl file."""
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValidationFailure(f"{path}: root must be an object")
        yield str(path), value
        return

    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValidationFailure(f"{path}:{line_number}: line must be an object")
                yield f"{path}:{line_number}", value
        return

    raise ValidationFailure(f"unsupported extension: {path}")


def discover_inputs(paths: list[Path]) -> list[Path]:
    """Expand files/directories while ignoring hidden and generated directories."""
    discovered: list[Path] = []
    for path in paths:
        if path.is_file():
            discovered.append(path)
        elif path.is_dir():
            discovered.extend(
                candidate
                for candidate in sorted(path.rglob("*"))
                if candidate.is_file() and candidate.suffix.lower() in {".json", ".jsonl"}
            )
        else:
            raise FileNotFoundError(path)
    return discovered
