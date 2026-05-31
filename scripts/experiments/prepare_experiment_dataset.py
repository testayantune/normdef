#!/usr/bin/env python3
"""
Prepare NormDef-FR v0.6 experimental datasets.

Inputs:
    data/normdef_fr_v0_6_gold.jsonl
    data/annotation/annotation_batch_v0_2_reviewed.jsonl  optional
    data/annotation/annotation_batch_v0_3_reviewed.jsonl  optional
    data/annotation/annotation_batch_v0_4_reviewed.jsonl  optional
    data/annotation/annotation_batch_v0_5_reviewed.jsonl  optional
    data/annotation/annotation_batch_v0_6_reviewed.jsonl  optional
    data/candidates/candidate_definition_articles_low_clean.jsonl optional

Outputs:
    data/experiments/v0_6/normdef_v0_6_gold_instances.jsonl
    data/experiments/v0_6/normdef_v0_6_term_definition_extraction.jsonl
    data/experiments/v0_6/normdef_v0_6_candidate_validation.jsonl
    data/experiments/v0_6/normdef_v0_6_article_classification.jsonl
    data/experiments/v0_6/normdef_v0_6_experiment_summary.json

Usage:
    python scripts/prepare_experiment_dataset.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GOLD_FILE = PROJECT_ROOT / "data" / "normdef_fr_v0_6_gold.jsonl"
CANDIDATE_ARTICLES_FILE = PROJECT_ROOT / "data" / "candidates" / "candidate_definition_articles_low_clean.jsonl"

REVIEWED_FILES = [
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_2_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_3_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_4_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_6_reviewed.jsonl",
]

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6"

OUTPUT_GOLD = OUTPUT_DIR / "normdef_v0_6_gold_instances.jsonl"
OUTPUT_EXTRACTION = OUTPUT_DIR / "normdef_v0_6_term_definition_extraction.jsonl"
OUTPUT_CANDIDATE_VALIDATION = OUTPUT_DIR / "normdef_v0_6_candidate_validation.jsonl"
OUTPUT_ARTICLE_CLASSIFICATION = OUTPUT_DIR / "normdef_v0_6_article_classification.jsonl"
OUTPUT_SUMMARY = OUTPUT_DIR / "normdef_v0_6_experiment_summary.json"

ACCEPTED_LABELS = {"valid_definition", "partial"}
INVALID_LABELS = {"invalid"}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\xa0", " ")
    text = text.replace("\u2028", "\n")
    text = text.replace("\u2029", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = text.lower()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,")


def normalize_article_number(value: Any) -> str:
    text = normalize_key(value)
    if text in {"article liminaire", "art liminaire", "art. liminaire"}:
        return "liminaire"
    return text


def article_key(row: dict[str, Any]) -> str:
    article_id = normalize_key(row.get("article_id"))
    if article_id:
        return f"article_id::{article_id}"

    source_file = normalize_key(row.get("source_file"))
    if source_file:
        return f"source_file::{source_file}"

    source_code = normalize_key(row.get("source_code"))
    article_number = normalize_article_number(row.get("article_number"))
    return f"source_article::{source_code}::{article_number}"


def load_jsonl(path: Path, required: bool = False) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        print(f"[WARN] Optional file not found, skipped: {path}")
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path.name} line {line_number}: expected JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def first_non_empty(row: dict[str, Any], *fields: str) -> Any:
    for field in fields:
        value = row.get(field)
        if clean_text(value) is not None:
            return value
    return None


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(clean_text(row.get(field)) or "unknown" for row in rows).most_common())


def make_gold_instances(gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in gold_rows:
        out.append({
            "instance_id": row.get("definition_id"),
            "definition_id": row.get("definition_id"),
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "source_file": clean_text(row.get("source_file")),
            "article_key": article_key(row),
            "term": clean_text(row.get("term")),
            "definition": clean_text(row.get("definition")),
            "defined_subject": clean_text(row.get("defined_subject")),
            "raw_body": clean_text(row.get("raw_body")),
            "pattern": clean_text(row.get("pattern")),
            "definition_type": clean_text(row.get("definition_type")),
            "scope_text": clean_text(row.get("scope_text")),
            "scope_label": clean_text(row.get("scope_label")),
            "inferred_scope": clean_text(row.get("inferred_scope")),
            "annotation_source": clean_text(row.get("annotation_source")),
            "manual_label": clean_text(row.get("manual_label")),
        })
    return out


def make_extraction_examples(gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in gold_rows:
        raw_body = clean_text(row.get("raw_body"))
        term = clean_text(row.get("term"))
        definition = clean_text(row.get("definition"))
        if not raw_body or not term or not definition:
            continue
        out.append({
            "example_id": row.get("definition_id"),
            "task": "term_definition_extraction",
            "input_text": raw_body,
            "target_term": term,
            "target_definition": definition,
            "target_defined_subject": clean_text(row.get("defined_subject")),
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "article_key": article_key(row),
            "pattern": clean_text(row.get("pattern")),
            "definition_type": clean_text(row.get("definition_type")),
            "scope_label": clean_text(row.get("scope_label")),
        })
    return out


def normalize_label(value: Any) -> str | None:
    text = clean_text(value)
    return text.lower().strip() if text else None


def make_candidate_validation_examples(reviewed_files: list[Path]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for path in reviewed_files:
        for row in load_jsonl(path, required=False):
            label = normalize_label(row.get("manual_label"))
            if label not in ACCEPTED_LABELS and label not in INVALID_LABELS:
                continue

            candidate_id = clean_text(row.get("candidate_definition_id")) or clean_text(row.get("definition_id"))
            if not candidate_id:
                candidate_id = f"{path.stem}:{len(out)+1}"
            if candidate_id in seen:
                continue
            seen.add(candidate_id)

            term = clean_text(first_non_empty(row, "term_candidate", "term", "gold_term"))
            definition = clean_text(first_non_empty(row, "definition_candidate", "definition", "gold_definition"))
            raw_body = clean_text(row.get("raw_body"))

            parts = []
            if term:
                parts.append(f"TERM: {term}")
            if definition:
                parts.append(f"DEFINITION: {definition}")
            if raw_body:
                parts.append(f"CONTEXT: {raw_body}")

            input_text = "\n".join(parts).strip()
            if not input_text:
                continue

            accepted = 1 if label in ACCEPTED_LABELS else 0

            out.append({
                "example_id": candidate_id,
                "task": "candidate_validation",
                "input_text": input_text,
                "candidate_term": term,
                "candidate_definition": definition,
                "raw_body": raw_body,
                "label": "accepted" if accepted else "invalid",
                "binary_label": accepted,
                "manual_label": label,
                "source_code": clean_text(row.get("source_code")),
                "article_number": clean_text(row.get("article_number")),
                "article_id": clean_text(row.get("article_id")),
                "article_key": article_key(row),
                "pattern": clean_text(row.get("pattern")),
                "definition_type": clean_text(row.get("definition_type")),
                "source_review_file": str(path),
            })
    return out


def make_article_classification_examples(gold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positives_by_key = {}
    for row in gold_rows:
        key = article_key(row)
        if key in positives_by_key:
            continue
        raw_body = clean_text(row.get("raw_body"))
        if not raw_body:
            continue
        positives_by_key[key] = {
            "example_id": f"article_pos_{len(positives_by_key)+1:05d}",
            "task": "article_definition_detection",
            "input_text": raw_body,
            "label": "definition_article",
            "binary_label": 1,
            "article_key": key,
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "source_file": clean_text(row.get("source_file")),
            "origin": "gold_positive",
        }

    positives = list(positives_by_key.values())
    positive_keys = set(positives_by_key.keys())
    max_negatives = int(len(positives) * 1.2)

    negatives = []
    for row in load_jsonl(CANDIDATE_ARTICLES_FILE, required=False):
        key = article_key(row)
        if key in positive_keys:
            continue
        text = clean_text(row.get("text") or row.get("raw_body"))
        if not text:
            continue
        negatives.append({
            "example_id": f"article_neg_{len(negatives)+1:05d}",
            "task": "article_definition_detection",
            "input_text": text,
            "label": "non_definition_article",
            "binary_label": 0,
            "article_key": key,
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "source_file": clean_text(row.get("source_file")),
            "origin": "low_clean_candidate_not_in_gold",
        })
        if len(negatives) >= max_negatives:
            break

    return positives + negatives


def main() -> int:
    gold_rows = load_jsonl(GOLD_FILE, required=True)

    gold_instances = make_gold_instances(gold_rows)
    extraction_examples = make_extraction_examples(gold_rows)
    candidate_validation_examples = make_candidate_validation_examples(REVIEWED_FILES)
    article_classification_examples = make_article_classification_examples(gold_rows)

    write_jsonl(OUTPUT_GOLD, gold_instances)
    write_jsonl(OUTPUT_EXTRACTION, extraction_examples)
    write_jsonl(OUTPUT_CANDIDATE_VALIDATION, candidate_validation_examples)
    write_jsonl(OUTPUT_ARTICLE_CLASSIFICATION, article_classification_examples)

    summary = {
        "version": "v0.6",
        "input_gold_file": str(GOLD_FILE),
        "output_dir": str(OUTPUT_DIR),
        "counts": {
            "gold_rows_read": len(gold_rows),
            "gold_instances": len(gold_instances),
            "term_definition_extraction_examples": len(extraction_examples),
            "candidate_validation_examples": len(candidate_validation_examples),
            "article_classification_examples": len(article_classification_examples),
            "article_classification_positive": sum(1 for x in article_classification_examples if x["binary_label"] == 1),
            "article_classification_negative": sum(1 for x in article_classification_examples if x["binary_label"] == 0),
        },
        "gold_distribution": {
            "source_code": distribution(gold_instances, "source_code"),
            "pattern": distribution(gold_instances, "pattern"),
            "definition_type": distribution(gold_instances, "definition_type"),
            "scope_label": distribution(gold_instances, "scope_label"),
            "annotation_source": distribution(gold_instances, "annotation_source"),
        },
        "candidate_validation_distribution": {
            "binary_label": distribution(candidate_validation_examples, "binary_label"),
            "manual_label": distribution(candidate_validation_examples, "manual_label"),
            "pattern": distribution(candidate_validation_examples, "pattern"),
        },
        "article_classification_distribution": {
            "binary_label": distribution(article_classification_examples, "binary_label"),
            "origin": distribution(article_classification_examples, "origin"),
            "source_code": distribution(article_classification_examples, "source_code"),
        },
        "notes": [
            "Pattern classification is treated as descriptive analysis, not as a main supervised task.",
            "Article negatives are automatically selected from low_clean candidate articles not represented in the gold set; report them as weak negatives.",
            "Next step: create stratified train/dev/test splits or 5-fold cross-validation splits.",
        ],
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Gold input: {GOLD_FILE}")
    print(f"Output dir: {OUTPUT_DIR}")
    print()
    print(f"Gold instances: {len(gold_instances)}")
    print(f"Term-definition extraction examples: {len(extraction_examples)}")
    print(f"Candidate validation examples: {len(candidate_validation_examples)}")
    print(f"Article classification examples: {len(article_classification_examples)}")
    print(f"- positives: {sum(1 for x in article_classification_examples if x['binary_label'] == 1)}")
    print(f"- negatives: {sum(1 for x in article_classification_examples if x['binary_label'] == 0)}")
    print()
    print(f"Wrote: {OUTPUT_GOLD}")
    print(f"Wrote: {OUTPUT_EXTRACTION}")
    print(f"Wrote: {OUTPUT_CANDIDATE_VALIDATION}")
    print(f"Wrote: {OUTPUT_ARTICLE_CLASSIFICATION}")
    print(f"Wrote: {OUTPUT_SUMMARY}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
