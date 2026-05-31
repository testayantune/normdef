#!/usr/bin/env python3
"""
Build a certified article-level classification dataset for NormDef-FR v0.6.

Inputs:
    data/experiments/v0_6/normdef_v0_6_article_classification.jsonl
        -> positive definition articles, binary_label = 1

    data/candidates/candidate_true_negative.jsonl
        -> certified/proposed true negatives

Outputs:
    data/experiments/v0_6/certified_article_classification/article_classification_certified.jsonl
    data/experiments/v0_6/certified_article_classification/certified_article_classification_summary.json

    data/experiments/v0_6/certified_article_classification/splits/train.jsonl
    data/experiments/v0_6/certified_article_classification/splits/dev.jsonl
    data/experiments/v0_6/certified_article_classification/splits/test.jsonl
    data/experiments/v0_6/certified_article_classification/splits/split_summary.json

Usage:
    python scripts/build_certified_article_classification_dataset.py
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ARTICLE_CLASSIFICATION_FILE = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "normdef_v0_6_article_classification.jsonl"
TRUE_NEGATIVE_FILE = PROJECT_ROOT / "data" / "candidates" / "candidate_true_negative.jsonl"

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "certified_article_classification"
OUTPUT_DATASET = OUTPUT_DIR / "article_classification_certified.jsonl"
OUTPUT_SUMMARY = OUTPUT_DIR / "certified_article_classification_summary.json"

SPLIT_DIR = OUTPUT_DIR / "splits"
TRAIN_FILE = SPLIT_DIR / "train.jsonl"
DEV_FILE = SPLIT_DIR / "dev.jsonl"
TEST_FILE = SPLIT_DIR / "test.jsonl"
SPLIT_SUMMARY = SPLIT_DIR / "split_summary.json"

RANDOM_SEED = 2026
TRAIN_RATIO = 0.70
DEV_RATIO = 0.15


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\xa0", " ")
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_key(value: Any) -> str:
    text = clean_text(value).lower()
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,")


def make_article_key(row: dict[str, Any]) -> str:
    existing = clean_text(row.get("article_key"))
    if existing:
        return existing

    article_id = normalize_key(row.get("article_id"))
    if article_id:
        return f"article_id::{article_id}"

    source_file = normalize_key(row.get("source_file"))
    if source_file:
        return f"source_file::{source_file}"

    source_code = normalize_key(row.get("source_code"))
    article_number = normalize_key(row.get("article_number"))
    return f"source_article::{source_code}::{article_number}"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

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


def unique_by_article_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []

    for row in rows:
        key = make_article_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)

    return out


def prepare_positive_rows(rows: list[dict[str, Any]], n_needed: int) -> list[dict[str, Any]]:
    positives = [row for row in rows if int(row.get("binary_label", -1)) == 1]
    positives = unique_by_article_key(positives)

    if len(positives) < n_needed:
        raise RuntimeError(f"Not enough positive articles: need {n_needed}, found {len(positives)}")

    rng = random.Random(RANDOM_SEED)
    rng.shuffle(positives)
    selected = positives[:n_needed]

    out = []
    for idx, row in enumerate(selected, start=1):
        out.append({
            "example_id": f"cert_pos_{idx:05d}",
            "task": "article_definition_detection_certified",
            "input_text": clean_text(row.get("input_text") or row.get("text") or row.get("raw_body")),
            "label": "definition_article",
            "binary_label": 1,
            "article_key": make_article_key(row),
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "source_file": clean_text(row.get("source_file")),
            "origin": "gold_positive",
            "certification": "gold_definition_article",
        })

    return out


def prepare_negative_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = unique_by_article_key(rows)
    out = []
    skipped_empty_text = 0

    for row in rows:
        text = clean_text(row.get("input_text") or row.get("text") or row.get("raw_body"))

        if not text:
            skipped_empty_text += 1
            continue

        out.append({
            "example_id": f"cert_neg_{len(out) + 1:05d}",
            "task": "article_definition_detection_certified",
            "input_text": text,
            "label": "certified_true_negative",
            "binary_label": 0,
            "article_key": make_article_key(row),
            "source_code": clean_text(row.get("source_code")),
            "article_number": clean_text(row.get("article_number")),
            "article_id": clean_text(row.get("article_id")),
            "source_file": clean_text(row.get("source_file")),
            "origin": "certified_true_negative_pool",
            "certification": clean_text(row.get("human_label")) or "true_negative_candidate",
            "candidate_score": row.get("candidate_score"),
            "noise_risk": row.get("noise_risk"),
            "matched_definition_patterns": row.get("matched_definition_patterns"),
            "matched_pattern_categories": row.get("matched_pattern_categories"),
        })

    if skipped_empty_text:
        print(f"[WARN] Skipped negative rows with empty text: {skipped_empty_text}")

    return out


def group_rows_by_article(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for idx, row in enumerate(rows):
        key = clean_text(row.get("article_key")) or f"row::{idx}"
        grouped[key].append(row)

    groups = []
    for key, group_rows in grouped.items():
        labels = [int(row.get("binary_label")) for row in group_rows]
        label = Counter(labels).most_common(1)[0][0]
        groups.append({"group_key": key, "label": label, "rows": group_rows, "size": len(group_rows)})

    return groups


def stratified_group_split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(RANDOM_SEED)
    groups = group_rows_by_article(rows)

    groups_by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        groups_by_label[int(group["label"])].append(group)

    train_groups = []
    dev_groups = []
    test_groups = []

    for label, label_groups in groups_by_label.items():
        rng.shuffle(label_groups)
        n = len(label_groups)
        n_train = int(round(n * TRAIN_RATIO))
        n_dev = int(round(n * DEV_RATIO))

        if n >= 3:
            n_train = min(max(n_train, 1), n - 2)
            n_dev = min(max(n_dev, 1), n - n_train - 1)

        train_groups.extend(label_groups[:n_train])
        dev_groups.extend(label_groups[n_train:n_train + n_dev])
        test_groups.extend(label_groups[n_train + n_dev:])

    rng.shuffle(train_groups)
    rng.shuffle(dev_groups)
    rng.shuffle(test_groups)

    def flatten(groups_: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for group in groups_:
            out.extend(group["rows"])
        return out

    return flatten(train_groups), flatten(dev_groups), flatten(test_groups)


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field, "unknown")) for row in rows).most_common())


def article_overlap(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> int:
    keys_a = {row.get("article_key") for row in a if row.get("article_key")}
    keys_b = {row.get("article_key") for row in b if row.get("article_key")}
    return len(keys_a & keys_b)


def main() -> int:
    original_article_rows = load_jsonl(ARTICLE_CLASSIFICATION_FILE)
    true_negative_rows_raw = load_jsonl(TRUE_NEGATIVE_FILE)

    negatives = prepare_negative_rows(true_negative_rows_raw)
    positives = prepare_positive_rows(original_article_rows, n_needed=len(negatives))

    dataset = positives + negatives
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(dataset)

    train, dev, test = stratified_group_split(dataset)

    write_jsonl(OUTPUT_DATASET, dataset)
    write_jsonl(TRAIN_FILE, train)
    write_jsonl(DEV_FILE, dev)
    write_jsonl(TEST_FILE, test)

    summary = {
        "version": "v0.6",
        "task": "article_definition_detection_certified",
        "input_positive_file": str(ARTICLE_CLASSIFICATION_FILE),
        "input_true_negative_file": str(TRUE_NEGATIVE_FILE),
        "output_dataset": str(OUTPUT_DATASET),
        "random_seed": RANDOM_SEED,
        "counts": {
            "original_article_rows_read": len(original_article_rows),
            "true_negative_rows_read": len(true_negative_rows_raw),
            "certified_negatives_kept": len(negatives),
            "gold_positives_sampled": len(positives),
            "total_dataset_rows": len(dataset),
            "train": len(train),
            "dev": len(dev),
            "test": len(test),
        },
        "label_distribution": {
            "all": distribution(dataset, "binary_label"),
            "train": distribution(train, "binary_label"),
            "dev": distribution(dev, "binary_label"),
            "test": distribution(test, "binary_label"),
        },
        "source_code_distribution_top30": {
            "all": dict(Counter(row.get("source_code", "unknown") for row in dataset).most_common(30)),
            "positive": dict(Counter(row.get("source_code", "unknown") for row in positives).most_common(30)),
            "negative": dict(Counter(row.get("source_code", "unknown") for row in negatives).most_common(30)),
        },
        "article_overlap": {
            "train_dev": article_overlap(train, dev),
            "train_test": article_overlap(train, test),
            "dev_test": article_overlap(dev, test),
        },
        "notes": [
            "This dataset replaces weak negatives with certified/proposed true negatives.",
            "The final dataset is balanced by sampling the same number of positive articles as certified negatives.",
            "Splits are grouped by article_key to reduce leakage.",
            "If certification is only model-assisted, report negatives as certified or manually verified according to the actual validation protocol.",
        ],
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    split_summary = {
        "dataset": str(OUTPUT_DATASET),
        "splits": {"train": str(TRAIN_FILE), "dev": str(DEV_FILE), "test": str(TEST_FILE)},
        "counts": summary["counts"],
        "label_distribution": summary["label_distribution"],
        "article_overlap": summary["article_overlap"],
    }

    SPLIT_SUMMARY.write_text(json.dumps(split_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Positive source: {ARTICLE_CLASSIFICATION_FILE}")
    print(f"True negative source: {TRUE_NEGATIVE_FILE}")
    print()
    print(f"Certified negatives kept: {len(negatives)}")
    print(f"Gold positives sampled:   {len(positives)}")
    print(f"Total dataset rows:       {len(dataset)}")
    print()
    print(f"Train: {len(train)} | labels: {distribution(train, 'binary_label')}")
    print(f"Dev:   {len(dev)} | labels: {distribution(dev, 'binary_label')}")
    print(f"Test:  {len(test)} | labels: {distribution(test, 'binary_label')}")
    print(f"Article overlap: {summary['article_overlap']}")
    print()
    print(f"Wrote dataset: {OUTPUT_DATASET}")
    print(f"Wrote summary: {OUTPUT_SUMMARY}")
    print(f"Wrote splits:  {SPLIT_DIR}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
