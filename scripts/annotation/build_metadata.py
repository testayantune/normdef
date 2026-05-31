#!/usr/bin/env python3
"""
Build data/metadata.json from data/normv1.0.json.

Run from the project root or from anywhere:
    python scripts/build_metadata.py

Expected project layout:
    normdef_automation/
    ├── data/
    │   ├── normdef_fr_v0_1_pilot.jsonl
    │   └── metadata.json
    └── scripts/
        └── build_metadata.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_JSONL = PROJECT_ROOT / "data" / "normdef_fr_v0_5_gold.jsonl"
OUTPUT_JSON = PROJECT_ROOT / "data" / "metadata_v0_5.json"


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

            rows.append(obj)

    return rows


def main() -> int:
    rows = load_jsonl(INPUT_JSONL)

    source_articles = sorted(
        {
            f"{row.get('source_code', 'UNKNOWN')} — {row.get('article_number', 'UNKNOWN')}"
            for row in rows
        }
    )

    metadata = {
        "dataset_name": "NormDef-FR",
        "version": "0.1-pilot",
        "language": "fr",
        "domain": "French legal codes",
        "task": "term-definition-scope extraction",
        "format": "jsonl",
        "annotation_schema_version": "0.1",
        "input_file": str(INPUT_JSONL.relative_to(PROJECT_ROOT)),
        "number_of_source_articles": len(source_articles),
        "number_of_definitions": len(rows),
        "source_articles": source_articles,
        "source_code_distribution": dict(Counter(row.get("source_code") for row in rows)),
        "scope_label_distribution": dict(Counter(row.get("scope_label") for row in rows)),
        "inferred_scope_distribution": dict(Counter(row.get("inferred_scope") for row in rows)),
        "definition_type_distribution": dict(Counter(row.get("definition_type") for row in rows)),
        "pattern_distribution": dict(Counter(row.get("pattern") for row in rows)),
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Input: {INPUT_JSONL}")
    print(f"Entries: {len(rows)}")
    print(f"Metadata written to: {OUTPUT_JSON}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
