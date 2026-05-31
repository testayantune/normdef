#!/usr/bin/env python3
"""
Validate data/normdef_fr_v0_1_pilot.jsonl.

Run from the project root or from anywhere:
    python scripts/validate_normdef_schema.py

Expected project layout:
    normdef_automation/
    ├── data/
    │   └── normdef_fr_v0_1_pilot.jsonl
    └── scripts/
        └── validate_normdef_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_JSONL = PROJECT_ROOT / "data" / "normdef_fr_v0_6_gold.jsonl"
INPUT_FILE = INPUT_JSONL
REQUIRED_FIELDS = [
    "definition_id",
    "source_code",
    "article_number",
    "item_number",
    "defined_subject",
    "term",
    "definition",
    "scope_text",
    "scope_label",
    "inferred_scope",
    "pattern",
    "definition_type",
    "raw_body",
]

ALLOWED_SCOPE_LABELS = {
    "article",
    "section",
    "chapitre",
    "titre",
    "livre",
    "code",
    "unspecified",
}

ALLOWED_INFERRED_SCOPES = {
    "article",
    "section",
    "chapitre",
    "titre",
    "livre",
    "code",
    "unspecified",
    None,
}

ALLOWED_DEFINITION_TYPES = {
    "explicit",
    "explicit_subitem",
    "explicit_internal",
    "explicit_enumerative",
    "explicit_qualification",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_number}: invalid JSON: {exc}") from exc

            if not isinstance(obj, dict):
                raise ValueError(
                    f"Line {line_number}: expected JSON object, got {type(obj).__name__}"
                )

            obj["__line_number"] = line_number
            rows.append(obj)

    return rows


def is_empty_text(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def validate(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for row in rows:
        line = row.get("__line_number", "?")
        definition_id = row.get("definition_id", f"line_{line}")

        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            errors.append(f"{definition_id} / line {line}: missing fields: {missing}")
            continue

        if definition_id in seen_ids:
            errors.append(f"{definition_id} / line {line}: duplicate definition_id")
        seen_ids.add(definition_id)

        for field in [
            "definition_id",
            "source_code",
            "article_number",
            "term",
            "definition",
            "pattern",
            "definition_type",
            "raw_body",
        ]:
            if is_empty_text(row.get(field)):
                errors.append(
                    f"{definition_id} / line {line}: empty required text field `{field}`"
                )

        if row.get("scope_label") not in ALLOWED_SCOPE_LABELS:
            errors.append(
                f"{definition_id} / line {line}: invalid scope_label `{row.get('scope_label')}`"
            )

        if row.get("inferred_scope") not in ALLOWED_INFERRED_SCOPES:
            errors.append(
                f"{definition_id} / line {line}: invalid inferred_scope `{row.get('inferred_scope')}`"
            )

        if row.get("definition_type") not in ALLOWED_DEFINITION_TYPES:
            errors.append(
                f"{definition_id} / line {line}: invalid definition_type `{row.get('definition_type')}`"
            )

        if row.get("scope_text") is None and row.get("scope_label") != "unspecified":
            warnings.append(
                f"{definition_id} / line {line}: scope_text is null but scope_label is `{row.get('scope_label')}`"
            )

        if row.get("definition_type") == "explicit_qualification" and is_empty_text(
            row.get("defined_subject")
        ):
            errors.append(
                f"{definition_id} / line {line}: explicit_qualification requires non-empty defined_subject"
            )

        if row.get("definition_type") != "explicit_qualification" and not is_empty_text(
            row.get("defined_subject")
        ):
            warnings.append(
                f"{definition_id} / line {line}: defined_subject is usually null unless definition_type is explicit_qualification"
            )

        term = row.get("term")
        raw_body = row.get("raw_body")
        if isinstance(term, str) and isinstance(raw_body, str):
            if term.strip() and term.strip() not in raw_body:
                warnings.append(
                    f"{definition_id} / line {line}: term not found exactly in raw_body: `{term}`"
                )

        definition = row.get("definition")
        if isinstance(definition, str) and isinstance(raw_body, str):
            definition_prefix = definition.strip()[:40]
            if definition_prefix and definition_prefix not in raw_body:
                warnings.append(
                    f"{definition_id} / line {line}: definition prefix not found exactly in raw_body"
                )

    return errors, warnings


def main() -> int:
    try:
        rows = load_jsonl(INPUT_JSONL)
        errors, warnings = validate(rows)
    except Exception as exc:
        print(f"Validation failed before schema checks: {exc}", file=sys.stderr)
        return 1

    print(f"File: {INPUT_JSONL}")
    print(f"Entries: {len(rows)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\nERRORS")
        for error in errors:
            print(f"- {error}")

    if warnings:
        print("\nWARNINGS")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        return 1

    print("\nSchema validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
