#!/usr/bin/env python3
"""
Build NormDef-FR v0.2 gold annotations from reviewed draft definitions.

Input:
    data/annotation/annotation_batch_v0_2_reviewed.jsonl

Output:
    data/annotation/normdef_fr_v0_2_gold_from_review.jsonl
    data/annotation/normdef_fr_v0_2_rejected_from_review.jsonl
    data/annotation/normdef_fr_v0_2_review_summary.json

Usage:
    python scripts/build_gold_from_review.py

Rules:
    - Keep manual_label = valid_definition or partial as gold records.
    - Export manual_label = invalid or unsure separately for error analysis.
    - Use gold_* fields as authoritative annotation fields.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_reviewed.jsonl"

OUTPUT_GOLD = PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_5_gold_from_review.jsonl"
OUTPUT_REJECTED = PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_5_rejected_from_review.jsonl"
OUTPUT_SUMMARY = PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_5_review_summary.json"

VALID_GOLD_LABELS = {"valid_definition", "partial"}
REJECTED_LABELS = {"invalid", "unsure"}


def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Load JSONL records one by one."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}\n"
            "Expected reviewed annotations from scripts/review_draft_definitions_gui.py."
        )

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] Line {line_number}: invalid JSON: {exc}")
                continue

            if not isinstance(row, dict):
                print(f"[WARN] Line {line_number}: expected JSON object")
                continue

            row["__line_number"] = line_number
            yield row


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


def safe_id_part(value: Any) -> str:
    """Create a safe ID fragment."""
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


def make_gold_definition_id(row: dict[str, Any], index: int) -> str:
    """Create a stable gold definition ID."""
    source = safe_id_part(row.get("source_code"))[:35]
    article = safe_id_part(row.get("article_number"))[:20]
    article_id = str(row.get("article_id") or "NOID").replace("LEGIARTI", "ARTI")
    return f"NORMDEF_FR_V0_2_{source}_{article}_{article_id}_{index:04d}"


def make_gold_record(row: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Convert a reviewed valid/partial draft into a gold annotation record."""
    manual_label = clean_text(row.get("manual_label"))

    if manual_label not in VALID_GOLD_LABELS:
        return None

    gold_term = clean_text(row.get("gold_term"))
    gold_definition = clean_text(row.get("gold_definition"))

    if not gold_term or not gold_definition:
        print(
            f"[WARN] {row.get('candidate_definition_id')} has manual_label={manual_label} "
            "but missing gold_term or gold_definition. Skipped."
        )
        return None

    gold_scope_text = clean_text(row.get("gold_scope_text"))
    gold_scope_label = clean_text(row.get("gold_scope_label")) or "unspecified"
    gold_inferred_scope = clean_text(row.get("gold_inferred_scope")) or "article"
    gold_definition_type = clean_text(row.get("gold_definition_type")) or "explicit"

    return {
        "definition_id": make_gold_definition_id(row, index),
        "candidate_definition_id": row.get("candidate_definition_id"),

        "source_code": row.get("source_code"),
        "article_number": row.get("article_number"),
        "article_id": row.get("article_id"),
        "etat": row.get("etat"),
        "date_debut": row.get("date_debut"),
        "date_fin": row.get("date_fin"),
        "source_file": row.get("source_file"),

        "item_number": row.get("item_number"),
        "term": gold_term,
        "definition": gold_definition,

        "scope_text": gold_scope_text,
        "scope_label": gold_scope_label,
        "inferred_scope": gold_inferred_scope,

        "pattern": row.get("pattern"),
        "definition_type": gold_definition_type,
        "raw_body": row.get("raw_body"),

        "manual_label": manual_label,
        "sampling_stratum": row.get("sampling_stratum"),
        "noise_risk": row.get("noise_risk"),
        "matched_definition_patterns": row.get("matched_definition_patterns"),
        "matched_pattern_categories": row.get("matched_pattern_categories"),
        "candidate_score": row.get("candidate_score"),
        "extraction_confidence": row.get("extraction_confidence"),
        "correction_notes": clean_text(row.get("correction_notes")),
    }


def make_rejected_record(row: dict[str, Any]) -> dict[str, Any]:
    """Keep rejected/unsure records for error analysis."""
    row = dict(row)
    row.pop("__line_number", None)
    return row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write records to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    gold_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    label_counter: Counter[str] = Counter()
    gold_pattern_counter: Counter[str] = Counter()
    gold_source_counter: Counter[str] = Counter()
    gold_type_counter: Counter[str] = Counter()
    rejected_pattern_counter: Counter[str] = Counter()
    rejected_source_counter: Counter[str] = Counter()

    total = 0
    gold_index = 1

    for row in load_jsonl(INPUT_FILE):
        total += 1

        manual_label = clean_text(row.get("manual_label")) or "missing"
        label_counter[manual_label] += 1

        if manual_label in VALID_GOLD_LABELS:
            gold_record = make_gold_record(row, gold_index)
            if gold_record is not None:
                gold_rows.append(gold_record)
                gold_index += 1

                gold_pattern_counter[str(gold_record.get("pattern", "unknown"))] += 1
                gold_source_counter[str(gold_record.get("source_code", "unknown"))] += 1
                gold_type_counter[str(gold_record.get("definition_type", "unknown"))] += 1
            else:
                skipped_rows.append(make_rejected_record(row))

        elif manual_label in REJECTED_LABELS:
            rejected = make_rejected_record(row)
            rejected_rows.append(rejected)
            rejected_pattern_counter[str(rejected.get("pattern", "unknown"))] += 1
            rejected_source_counter[str(rejected.get("source_code", "unknown"))] += 1

        else:
            skipped_rows.append(make_rejected_record(row))

    write_jsonl(OUTPUT_GOLD, gold_rows)
    write_jsonl(OUTPUT_REJECTED, rejected_rows)

    total_reviewed = sum(label_counter[label] for label in VALID_GOLD_LABELS | REJECTED_LABELS)
    accepted = len(gold_rows)
    rejected = len(rejected_rows)

    precision_accept_partial = accepted / total_reviewed if total_reviewed else 0.0
    strict_valid = label_counter["valid_definition"]
    strict_precision_valid_only = strict_valid / total_reviewed if total_reviewed else 0.0

    summary = {
        "input_file": str(INPUT_FILE),
        "output_gold": str(OUTPUT_GOLD),
        "output_rejected": str(OUTPUT_REJECTED),
        "total_rows_read": total,
        "total_reviewed_rows": total_reviewed,
        "gold_rows": accepted,
        "rejected_rows": rejected,
        "skipped_or_missing_label_rows": len(skipped_rows),
        "manual_label_distribution": dict(label_counter),
        "precision_valid_plus_partial": precision_accept_partial,
        "precision_valid_only": strict_precision_valid_only,
        "gold_pattern_distribution": dict(gold_pattern_counter),
        "gold_definition_type_distribution": dict(gold_type_counter),
        "gold_source_code_distribution": dict(gold_source_counter),
        "rejected_pattern_distribution": dict(rejected_pattern_counter),
        "rejected_source_code_distribution": dict(rejected_source_counter),
    }

    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Input file: {INPUT_FILE}")
    print(f"Gold output: {OUTPUT_GOLD}")
    print(f"Rejected output: {OUTPUT_REJECTED}")
    print(f"Summary output: {OUTPUT_SUMMARY}")

    print(f"\nTotal rows read: {total}")
    print(f"Reviewed rows: {total_reviewed}")
    print(f"Gold rows created: {accepted}")
    print(f"Rejected rows: {rejected}")
    print(f"Skipped/missing label rows: {len(skipped_rows)}")

    print("\nManual label distribution:")
    for label, count in label_counter.most_common():
        print(f"- {label}: {count}")

    print("\nEvaluation:")
    print(f"- Precision valid + partial: {precision_accept_partial:.3f}")
    print(f"- Precision valid only:      {strict_precision_valid_only:.3f}")

    print("\nGold records by pattern:")
    for pattern, count in gold_pattern_counter.most_common():
        print(f"- {pattern}: {count}")

    print("\nGold records by definition type:")
    for definition_type, count in gold_type_counter.most_common():
        print(f"- {definition_type}: {count}")

    print("\nTop gold source codes:")
    for source_code, count in gold_source_counter.most_common(20):
        print(f"- {source_code}: {count}")

    print("\nRejected records by pattern:")
    for pattern, count in rejected_pattern_counter.most_common():
        print(f"- {pattern}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
