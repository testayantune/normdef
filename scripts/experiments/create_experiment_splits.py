#!/usr/bin/env python3
"""
Create stratified train/dev/test splits for NormDef-FR v0.6 experiments.

Inputs:
    data/experiments/v0_6/normdef_v0_6_term_definition_extraction.jsonl
    data/experiments/v0_6/normdef_v0_6_candidate_validation.jsonl
    data/experiments/v0_6/normdef_v0_6_article_classification.jsonl

Outputs:
    data/experiments/v0_6/splits/<task>/train.jsonl
    data/experiments/v0_6/splits/<task>/dev.jsonl
    data/experiments/v0_6/splits/<task>/test.jsonl
    data/experiments/v0_6/splits/split_summary.json

Usage:
    python scripts/create_experiment_splits.py

Split strategy:
    - article_classification:
        stratify by binary_label

    - candidate_validation:
        stratify by binary_label

    - term_definition_extraction:
        stratify by coarse pattern group

Important:
    The script tries to avoid leakage by grouping on article_key when possible.
    This means examples from the same article should not be spread across train/dev/test.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPERIMENT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6"

TASK_FILES = {
    "term_definition_extraction": EXPERIMENT_DIR / "normdef_v0_6_term_definition_extraction.jsonl",
    "candidate_validation": EXPERIMENT_DIR / "normdef_v0_6_candidate_validation.jsonl",
    "article_classification": EXPERIMENT_DIR / "normdef_v0_6_article_classification.jsonl",
}

OUTPUT_SPLIT_DIR = EXPERIMENT_DIR / "splits"
OUTPUT_SUMMARY = OUTPUT_SPLIT_DIR / "split_summary.json"

RANDOM_SEED = 2026
TRAIN_RATIO = 0.70
DEV_RATIO = 0.15
TEST_RATIO = 0.15


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


def clean_text(value: Any) -> str:
    if value is None:
        return "unknown"
    text = str(value).strip()
    return text if text else "unknown"


def coarse_pattern(pattern: Any) -> str:
    """
    Collapse sparse patterns into a few robust groups for stratification.
    This avoids split failures caused by rare classes.
    """
    p = clean_text(pattern)

    if p == "terme_colon_definition":
        return "colon_definition"

    if "s'entend de" in p:
        return "sentend_de"

    if "on entend par" in p:
        return "on_entend_par"

    if "défini" in p or "defini" in p:
        return "defini_comme"

    if "considéré" in p or "consideres" in p or "considérés" in p:
        return "qualification"

    return "other"


def stratification_label(task: str, row: dict[str, Any]) -> str:
    if task in {"article_classification", "candidate_validation"}:
        return str(row.get("binary_label", "unknown"))

    if task == "term_definition_extraction":
        return coarse_pattern(row.get("pattern"))

    return "all"


def group_rows_by_article(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Create article-level groups to reduce leakage.

    Each group has:
        group_key
        strat_label
        rows

    The group strat_label is the most frequent row label inside the group.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for idx, row in enumerate(rows):
        group_key = clean_text(row.get("article_key"))
        if group_key == "unknown":
            group_key = clean_text(row.get("article_id"))
        if group_key == "unknown":
            group_key = f"row::{idx}"

        grouped[group_key].append(row)

    groups = []

    for key, group_rows in grouped.items():
        labels = [row["_strat_label"] for row in group_rows]
        label = Counter(labels).most_common(1)[0][0]

        groups.append(
            {
                "group_key": key,
                "strat_label": label,
                "rows": group_rows,
                "size": len(group_rows),
            }
        )

    return groups


def split_groups_stratified(
    rows: list[dict[str, Any]],
    task: str,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Stratified split at article-group level.

    This is not a mathematically perfect stratified split, but it is robust:
        - groups by article_key to reduce leakage;
        - splits groups within each stratum;
        - preserves approximate train/dev/test ratios.
    """
    rng = random.Random(seed)

    prepared_rows = []
    for row in rows:
        row = dict(row)
        row["_strat_label"] = stratification_label(task, row)
        prepared_rows.append(row)

    groups = group_rows_by_article(prepared_rows)

    groups_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        groups_by_label[group["strat_label"]].append(group)

    train_groups = []
    dev_groups = []
    test_groups = []

    for label, label_groups in groups_by_label.items():
        rng.shuffle(label_groups)

        n = len(label_groups)
        n_train = int(round(n * TRAIN_RATIO))
        n_dev = int(round(n * DEV_RATIO))

        # Ensure non-empty dev/test for labels with enough groups.
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
            for row in group["rows"]:
                clean = {k: v for k, v in row.items() if not k.startswith("_")}
                out.append(clean)
        return out

    return flatten(train_groups), flatten(dev_groups), flatten(test_groups)


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field, "unknown")) for row in rows).most_common())


def strat_distribution(rows: list[dict[str, Any]], task: str) -> dict[str, int]:
    return dict(Counter(stratification_label(task, row) for row in rows).most_common())


def article_overlap(*splits: list[dict[str, Any]]) -> dict[str, Any]:
    sets = []

    for rows in splits:
        keys = {clean_text(row.get("article_key")) for row in rows if clean_text(row.get("article_key")) != "unknown"}
        sets.append(keys)

    train, dev, test = sets

    return {
        "train_dev_overlap": len(train & dev),
        "train_test_overlap": len(train & test),
        "dev_test_overlap": len(dev & test),
    }


def make_split_for_task(task: str, input_file: Path) -> dict[str, Any]:
    rows = load_jsonl(input_file)

    train, dev, test = split_groups_stratified(rows, task=task, seed=RANDOM_SEED)

    task_dir = OUTPUT_SPLIT_DIR / task
    write_jsonl(task_dir / "train.jsonl", train)
    write_jsonl(task_dir / "dev.jsonl", dev)
    write_jsonl(task_dir / "test.jsonl", test)

    summary = {
        "task": task,
        "input_file": str(input_file),
        "output_dir": str(task_dir),
        "counts": {
            "total": len(rows),
            "train": len(train),
            "dev": len(dev),
            "test": len(test),
        },
        "ratios": {
            "train": len(train) / len(rows) if rows else None,
            "dev": len(dev) / len(rows) if rows else None,
            "test": len(test) / len(rows) if rows else None,
        },
        "stratification_distribution": {
            "all": strat_distribution(rows, task),
            "train": strat_distribution(train, task),
            "dev": strat_distribution(dev, task),
            "test": strat_distribution(test, task),
        },
        "binary_label_distribution": {
            "all": distribution(rows, "binary_label"),
            "train": distribution(train, "binary_label"),
            "dev": distribution(dev, "binary_label"),
            "test": distribution(test, "binary_label"),
        } if task in {"article_classification", "candidate_validation"} else None,
        "pattern_distribution": {
            "all": distribution(rows, "pattern"),
            "train": distribution(train, "pattern"),
            "dev": distribution(dev, "pattern"),
            "test": distribution(test, "pattern"),
        },
        "source_code_distribution_top20": {
            "all": dict(Counter(str(row.get("source_code", "unknown")) for row in rows).most_common(20)),
            "train": dict(Counter(str(row.get("source_code", "unknown")) for row in train).most_common(20)),
            "dev": dict(Counter(str(row.get("source_code", "unknown")) for row in dev).most_common(20)),
            "test": dict(Counter(str(row.get("source_code", "unknown")) for row in test).most_common(20)),
        },
        "article_overlap": article_overlap(train, dev, test),
    }

    return summary


def main() -> int:
    OUTPUT_SPLIT_DIR.mkdir(parents=True, exist_ok=True)

    summaries = {}

    for task, input_file in TASK_FILES.items():
        print(f"Creating splits for {task}...")
        summaries[task] = make_split_for_task(task, input_file)

    global_summary = {
        "version": "v0.6",
        "random_seed": RANDOM_SEED,
        "split_ratios_requested": {
            "train": TRAIN_RATIO,
            "dev": DEV_RATIO,
            "test": TEST_RATIO,
        },
        "tasks": summaries,
        "notes": [
            "Splits are stratified approximately.",
            "Rows are grouped by article_key when possible to reduce leakage.",
            "Pattern classification is not a main task; pattern distributions are reported for split quality control.",
        ],
    }

    OUTPUT_SUMMARY.write_text(
        json.dumps(global_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Wrote split summary: {OUTPUT_SUMMARY}")

    for task, summary in summaries.items():
        counts = summary["counts"]
        print()
        print(f"{task}:")
        print(f"- total: {counts['total']}")
        print(f"- train: {counts['train']}")
        print(f"- dev:   {counts['dev']}")
        print(f"- test:  {counts['test']}")
        print(f"- article overlap: {summary['article_overlap']}")

        if summary.get("binary_label_distribution"):
            print(f"- binary all:   {summary['binary_label_distribution']['all']}")
            print(f"- binary train: {summary['binary_label_distribution']['train']}")
            print(f"- binary dev:   {summary['binary_label_distribution']['dev']}")
            print(f"- binary test:  {summary['binary_label_distribution']['test']}")

        print(f"- strat all:   {summary['stratification_distribution']['all']}")
        print(f"- strat train: {summary['stratification_distribution']['train']}")
        print(f"- strat dev:   {summary['stratification_distribution']['dev']}")
        print(f"- strat test:  {summary['stratification_distribution']['test']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
