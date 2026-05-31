#!/usr/bin/env python3
"""
Merge NormDef-FR v0.4 gold with v0.5 reviewed annotations.

Inputs:
    data/normdef_fr_v0_4_gold.jsonl
    data/annotation/normdef_fr_v0_5_gold_from_review.jsonl

Outputs:
    data/normdef_fr_v0_5_gold.jsonl
    data/normdef_fr_v0_5_duplicates_removed.jsonl
    data/metadata_merged_gold_v0_5.json

Usage:
    python scripts/merge_gold_v0_5.py

Important merge order:
    1. Load v0.4 gold.
    2. Load v0.5 review rows.
    3. Validate manual_label for v0.5 review rows:
        keep only valid_definition and partial.
        skip invalid, rejected, missing labels, etc.
    4. After this validation, deduplicate.

Deduplication:
    1. Exact definition duplicate:
        article_id + normalized term + normalized definition

       If article_id is missing:
        source_code + article_number + normalized term + normalized definition

    2. Project-level uniqueness rule:
        source_code + article_number + normalized term

       This is less aggressive than source_code + term:
       the same term may appear in the same source_code when it belongs
       to a different article_number.

Conflict rule:
    v0.4 gold wins when a conflict exists.
    v0.5 duplicate records are written to the duplicates file for audit.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

V0_4_GOLD_FILE = PROJECT_ROOT / "data" / "normdef_fr_v0_4_gold.jsonl"
V0_5_REVIEW_FILE = PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_5_gold_from_review.jsonl"

OUTPUT_JSONL = PROJECT_ROOT / "data" / "normdef_fr_v0_5_gold.jsonl"
OUTPUT_DUPLICATES = PROJECT_ROOT / "data" / "normdef_fr_v0_5_duplicates_removed.jsonl"
OUTPUT_METADATA = PROJECT_ROOT / "data" / "metadata_merged_gold_v0_5.json"

ACCEPTED_REVIEW_LABELS = {"valid_definition", "partial"}

FINAL_FIELD_ORDER = [
    "definition_id",
    "source_code",
    "article_number",
    "article_id",
    "etat",
    "date_debut",
    "date_fin",
    "item_number",
    "term",
    "defined_subject",
    "definition",
    "scope_text",
    "scope_label",
    "inferred_scope",
    "pattern",
    "definition_type",
    "raw_body",
    "source_file",
    "annotation_source",
    "manual_label",
    "candidate_definition_id",
    "correction_notes",
    "previous_definition_id",
]


def clean_text(value: Any) -> str | None:
    """Normalize empty strings and whitespace."""
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    value = value.replace("\xa0", " ")
    value = value.replace("\u2028", "\n")
    value = value.replace("\u2029", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s+\n", "\n", value)
    value = re.sub(r"\n\s+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value.strip() or None


def strip_accents(text: str) -> str:
    """Remove accents for robust matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_source_code(value: Any) -> str:
    """Normalize source_code."""
    text = clean_text(value) or ""
    text = text.lower()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")

    # Harmonize frequent source-code variants.
    text = text.replace("code rural (nouveau)", "code rural et de la pêche maritime")
    text = text.replace("code rural et de la peche maritime", "code rural et de la pêche maritime")

    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,")


def normalize_article_number(value: Any) -> str:
    """Normalize article_number."""
    text = clean_text(value) or ""
    text = text.lower()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .;:,")

    # Pilot may use Article liminaire while LEGI may use liminaire.
    if text in {"article liminaire", "art liminaire", "art. liminaire"}:
        return "liminaire"

    return text


def normalize_text(value: Any, remove_accents: bool = False) -> str:
    """Normalize text for deduplication."""
    text = clean_text(value) or ""
    text = text.lower()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")

    if remove_accents:
        text = strip_accents(text)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*'\s*", "'", text)
    return text.strip(" .;:,")


def normalize_term(value: Any) -> str:
    """Normalize term."""
    return normalize_text(value, remove_accents=True)


def safe_id_part(value: Any) -> str:
    """Create an ID-safe fragment."""
    value = str(value or "UNK").upper()

    replacements = {
        "É": "E", "È": "E", "Ê": "E", "Ë": "E",
        "À": "A", "Â": "A", "Ä": "A",
        "Î": "I", "Ï": "I",
        "Ô": "O", "Ö": "O",
        "Û": "U", "Ü": "U",
        "Ç": "C",
        "Œ": "OE",
    }

    for src, dst in replacements.items():
        value = value.replace(src, dst)

    value = re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    return value or "UNK"


def load_json_or_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    """
    Load either:
    - JSON array;
    - JSON object;
    - JSONL file.

    Returns a list of JSON objects.
    """
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        print(f"[WARN] File not found, skipped: {path}")
        return []

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        data = json.loads(text)

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            for key in ["data", "records", "definitions", "items"]:
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]

            return [data]

    except json.JSONDecodeError:
        pass

    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"[WARN] {path.name} line {line_number}: invalid JSON: {exc}")
            continue

        if isinstance(item, dict):
            rows.append(item)

    return rows


def make_definition_id(row: dict[str, Any], index: int) -> str:
    """Create a stable v0.5 merged definition ID."""
    source = safe_id_part(row.get("source_code"))[:35]
    article = safe_id_part(row.get("article_number"))[:20]
    article_id = str(row.get("article_id") or "NOID").replace("LEGIARTI", "ARTI")
    return f"NORMDEF_FR_V0_5_{source}_{article}_{article_id}_{index:05d}"


def accepted_by_manual_label(row: dict[str, Any], annotation_source: str) -> tuple[bool, str | None]:
    """
    Keep all rows from already-merged gold sources.
    For reviewed sources, keep only valid_definition and partial.

    This is done BEFORE deduplication.
    """
    manual_label = clean_text(row.get("manual_label"))

    if annotation_source.endswith("_gold"):
        return True, None

    if manual_label in ACCEPTED_REVIEW_LABELS:
        return True, None

    if manual_label is None:
        return False, "missing_manual_label"

    return False, f"rejected_manual_label:{manual_label}"


def standardize_record(row: dict[str, Any], annotation_source: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Standardize records into the final NormDef-FR schema.

    Supports both already-standardized gold records and reviewed draft records.
    Returns:
        (record, None) if kept;
        (None, reason) if skipped.
    """
    accepted, reason = accepted_by_manual_label(row, annotation_source)
    if not accepted:
        return None, reason

    term = clean_text(row.get("term") or row.get("gold_term") or row.get("term_candidate"))
    definition = clean_text(
        row.get("definition") or row.get("gold_definition") or row.get("definition_candidate")
    )

    if not term or not definition:
        return None, "missing_term_or_definition"

    scope_label = clean_text(row.get("scope_label") or row.get("gold_scope_label")) or "unspecified"
    inferred_scope = clean_text(row.get("inferred_scope") or row.get("gold_inferred_scope")) or "article"
    definition_type = clean_text(row.get("definition_type") or row.get("gold_definition_type")) or "explicit"

    standardized = {
        "definition_id": clean_text(row.get("definition_id") or row.get("gold_definition_id")),
        "source_code": clean_text(row.get("source_code")),
        "article_number": clean_text(row.get("article_number")),
        "article_id": clean_text(row.get("article_id")),
        "etat": clean_text(row.get("etat")),
        "date_debut": clean_text(row.get("date_debut")),
        "date_fin": clean_text(row.get("date_fin")),
        "item_number": clean_text(row.get("item_number")),
        "term": term,
        "defined_subject": clean_text(row.get("defined_subject")),
        "definition": definition,
        "scope_text": clean_text(row.get("scope_text") or row.get("gold_scope_text")),
        "scope_label": scope_label,
        "inferred_scope": inferred_scope,
        "pattern": clean_text(row.get("pattern")),
        "definition_type": definition_type,
        "raw_body": clean_text(row.get("raw_body")),
        "source_file": clean_text(row.get("source_file")),
        "annotation_source": annotation_source,
        "manual_label": clean_text(row.get("manual_label")),
        "candidate_definition_id": clean_text(row.get("candidate_definition_id")),
        "correction_notes": clean_text(row.get("correction_notes")),
        "previous_definition_id": clean_text(row.get("previous_definition_id") or row.get("definition_id")),
    }

    for optional_field in ["correction_status", "issue_reasons", "extraction_confidence"]:
        if optional_field in row and row.get(optional_field) is not None:
            standardized[optional_field] = row.get(optional_field)

    return standardized, None


def exact_dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """
    Exact duplicate key.

    Prefer article_id when available.
    Otherwise use source_code + article_number.
    """
    article_id = normalize_text(row.get("article_id"))
    term = normalize_term(row.get("term"))
    definition = normalize_text(row.get("definition"), remove_accents=True)

    if article_id:
        return ("article_id", article_id, term, definition)

    source_code = normalize_source_code(row.get("source_code"))
    article_number = normalize_article_number(row.get("article_number"))

    return ("source_article", f"{source_code}::{article_number}", term, definition)


def source_article_term_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """
    Project-level uniqueness key:
        source_code + article_number + normalized term

    This is less aggressive than source_code + term.
    It allows the same term to appear in the same source_code when it belongs
    to a different article_number.
    """
    return (
        normalize_source_code(row.get("source_code")),
        normalize_article_number(row.get("article_number")),
        normalize_term(row.get("term")),
    )


def ordered_record(row: dict[str, Any]) -> dict[str, Any]:
    """Return record with stable field order, preserving extra fields at the end."""
    out: dict[str, Any] = {}

    for key in FINAL_FIELD_ORDER:
        out[key] = row.get(key)

    for key, value in row.items():
        if key not in out:
            out[key] = value

    return out


def merge_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Counter]:
    """Load, validate, standardize, and deduplicate v0.4 + v0.5."""
    source_specs = [
        ("v0.4_gold", V0_4_GOLD_FILE),
        ("v0.5_review", V0_5_REVIEW_FILE),
    ]

    merged: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    seen_exact: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    seen_source_article_term: dict[tuple[str, str, str], dict[str, Any]] = {}

    stats: Counter = Counter()

    for annotation_source, path in source_specs:
        raw_rows = load_json_or_jsonl(path, required=True)
        stats[f"{annotation_source}_rows_read"] = len(raw_rows)

        for raw in raw_rows:
            standardized, skip_reason = standardize_record(raw, annotation_source)

            if standardized is None:
                stats[f"{annotation_source}_rows_skipped"] += 1
                if skip_reason:
                    stats[f"{annotation_source}_skipped_{skip_reason}"] += 1
                skipped.append(
                    {
                        "skip_reason": skip_reason or "unknown",
                        "source": annotation_source,
                        "record": raw,
                    }
                )
                continue

            # Deduplication happens only after validation/acceptance.
            exact_key = exact_dedupe_key(standardized)
            sat_key = source_article_term_key(standardized)

            duplicate_reason = None
            duplicate_of = None

            if exact_key in seen_exact:
                duplicate_reason = "exact_article_term_definition_duplicate"
                duplicate_of = seen_exact[exact_key]

            elif sat_key in seen_source_article_term:
                duplicate_reason = "existing_source_code_article_number_term"
                duplicate_of = seen_source_article_term[sat_key]

            if duplicate_reason:
                duplicates.append(
                    {
                        "duplicate_reason": duplicate_reason,
                        "duplicate_of_definition_id": duplicate_of.get("definition_id"),
                        "duplicate_of_source": duplicate_of.get("annotation_source"),
                        "duplicate_source": annotation_source,
                        "source_article_term_key": {
                            "source_code": sat_key[0],
                            "article_number": sat_key[1],
                            "term": sat_key[2],
                        },
                        "duplicate_record": standardized,
                    }
                )
                stats["duplicates_removed"] += 1
                stats[f"{annotation_source}_duplicates_removed"] += 1
                stats[f"{duplicate_reason}_removed"] += 1
                continue

            seen_exact[exact_key] = standardized
            seen_source_article_term[sat_key] = standardized
            merged.append(standardized)
            stats[f"{annotation_source}_rows_kept"] += 1

    for index, row in enumerate(merged, start=1):
        old_id = row.get("definition_id")
        row["previous_definition_id"] = row.get("previous_definition_id") or old_id
        row["definition_id"] = make_definition_id(row, index)

    merged = [ordered_record(row) for row in merged]

    return merged, duplicates, skipped, stats


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    merged, duplicates, skipped, stats = merge_sources()

    skipped_path = PROJECT_ROOT / "data" / "normdef_fr_v0_5_skipped_non_gold_rows.jsonl"

    write_jsonl(OUTPUT_JSONL, merged)
    write_jsonl(OUTPUT_DUPLICATES, duplicates)
    write_jsonl(skipped_path, skipped)

    source_counter = Counter(row.get("annotation_source", "unknown") for row in merged)
    code_counter = Counter(row.get("source_code", "unknown") for row in merged)
    pattern_counter = Counter(row.get("pattern", "unknown") for row in merged)
    type_counter = Counter(row.get("definition_type", "unknown") for row in merged)
    scope_counter = Counter(row.get("scope_label", "unknown") for row in merged)

    metadata = {
        "dataset_name": "NormDef-FR",
        "version": "0.5",
        "annotation_schema_version": "0.3",
        "language": "fr",
        "domain": "French legal codes",
        "task": "term-definition-scope extraction",
        "format": "jsonl",
        "number_of_definitions": len(merged),
        "input_files": {
            "v0.4_gold": str(V0_4_GOLD_FILE),
            "v0.5_review": str(V0_5_REVIEW_FILE),
        },
        "output_file": str(OUTPUT_JSONL),
        "duplicates_file": str(OUTPUT_DUPLICATES),
        "skipped_file": str(skipped_path),
        "accepted_review_labels": sorted(ACCEPTED_REVIEW_LABELS),
        "deduplication_order": [
            "manual label validation",
            "exact duplicate detection",
            "source_code + article_number + term duplicate detection",
        ],
        "deduplication_rules": [
            "article_id + normalized term + normalized definition",
            "fallback: source_code + article_number + normalized term + normalized definition",
            "project uniqueness: source_code + normalized article_number + normalized term",
        ],
        "merge_stats": dict(stats),
        "annotation_source_distribution": dict(source_counter),
        "source_code_distribution": dict(code_counter),
        "pattern_distribution": dict(pattern_counter),
        "definition_type_distribution": dict(type_counter),
        "scope_label_distribution": dict(scope_counter),
    }

    OUTPUT_METADATA.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Input v0.4 gold: {V0_4_GOLD_FILE}")
    print(f"Input v0.5 review: {V0_5_REVIEW_FILE}")
    print(f"Output merged gold: {OUTPUT_JSONL}")
    print(f"Output metadata: {OUTPUT_METADATA}")
    print(f"Duplicates removed file: {OUTPUT_DUPLICATES}")
    print(f"Skipped non-gold rows file: {skipped_path}")

    print(f"\nFinal gold definitions: {len(merged)}")
    print(f"Duplicates removed after validation: {len(duplicates)}")
    print(f"Skipped non-gold / invalid rows before dedupe: {len(skipped)}")

    print("\nRows by annotation source:")
    for source, count in source_counter.most_common():
        print(f"- {source}: {count}")

    print("\nMerge stats:")
    for key, value in sorted(stats.items()):
        print(f"- {key}: {value}")

    print("\nTop source codes:")
    for code, count in code_counter.most_common(25):
        print(f"- {code}: {count}")

    print("\nTop patterns:")
    for pattern, count in pattern_counter.most_common(25):
        print(f"- {pattern}: {count}")

    print("\nDefinition types:")
    for definition_type, count in type_counter.most_common():
        print(f"- {definition_type}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
