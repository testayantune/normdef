#!/usr/bin/env python3
"""
5-fold cross-validation for NormDef-FR v0.6 candidate validation using TF-IDF baselines.

Input:
    data/experiments/v0_6/normdef_v0_6_candidate_validation.jsonl

Outputs:
    data/experiments/v0_6/results/candidate_validation_tfidf_5fold_metrics.json
    data/experiments/v0_6/results/candidate_validation_tfidf_5fold_predictions.jsonl

Usage:
    python scripts/cross_validate_tfidf_candidate_validator.py
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "normdef_v0_6_candidate_validation.jsonl"

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "results"
OUTPUT_METRICS = OUTPUT_DIR / "candidate_validation_tfidf_5fold_metrics.json"
OUTPUT_PREDICTIONS = OUTPUT_DIR / "candidate_validation_tfidf_5fold_predictions.jsonl"

RANDOM_SEED = 2026
N_FOLDS = 5


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\xa0", " ")
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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


def rows_to_xy(rows: list[dict[str, Any]]) -> tuple[list[str], list[int]]:
    texts = [clean_text(row.get("input_text")) for row in rows]
    labels = [int(row.get("binary_label")) for row in rows]
    return texts, labels


def make_models() -> dict[str, Pipeline]:
    return {
        "tfidf_word_logreg": Pipeline(
            [
                ("tfidf", TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.95,
                    sublinear_tf=True,
                )),
                ("clf", LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                )),
            ]
        ),
        "tfidf_word_linear_svm": Pipeline(
            [
                ("tfidf", TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.95,
                    sublinear_tf=True,
                )),
                ("clf", LinearSVC(
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                )),
            ]
        ),
        "tfidf_char_linear_svm": Pipeline(
            [
                ("tfidf", TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_df=0.95,
                    sublinear_tf=True,
                )),
                ("clf", LinearSVC(
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                )),
            ]
        ),
    }


def article_key(row: dict[str, Any], idx: int) -> str:
    key = clean_text(row.get("article_key"))
    if key:
        return key
    article_id = clean_text(row.get("article_id"))
    if article_id:
        return f"article_id::{article_id}"
    return f"row::{idx}"


def group_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, row in enumerate(rows):
        grouped[article_key(row, idx)].append(row)

    groups = []
    for key, group_rows_ in grouped.items():
        labels = [int(r.get("binary_label")) for r in group_rows_]
        majority_label = Counter(labels).most_common(1)[0][0]
        groups.append({"group_key": key, "label": majority_label, "rows": group_rows_, "size": len(group_rows_)})
    return groups


def make_stratified_group_folds(rows: list[dict[str, Any]], n_folds: int, seed: int) -> list[list[dict[str, Any]]]:
    rng = random.Random(seed)
    groups = group_rows(rows)

    by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        by_label[int(group["label"])].append(group)

    fold_groups: list[list[dict[str, Any]]] = [[] for _ in range(n_folds)]

    for label, label_groups in by_label.items():
        rng.shuffle(label_groups)
        for group in sorted(label_groups, key=lambda g: g["size"], reverse=True):
            target_idx = min(range(n_folds), key=lambda i: sum(g["size"] for g in fold_groups[i]))
            fold_groups[target_idx].append(group)

    folds: list[list[dict[str, Any]]] = []
    for groups_in_fold in fold_groups:
        fold_rows = []
        for group in groups_in_fold:
            fold_rows.extend(group["rows"])
        folds.append(fold_rows)

    return folds


def evaluate_predictions(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=[0, 1], zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "accepted_f1": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
        "invalid_f1": f1_score(y_true, y_pred, pos_label=0, zero_division=0),
        "labels": {
            "0_invalid": {"precision": precision[0], "recall": recall[0], "f1": f1[0], "support": int(support[0])},
            "1_accepted": {"precision": precision[1], "recall": recall[1], "f1": f1[1], "support": int(support[1])},
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
    }


def summarize(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {
        "mean": mean(values),
        "std": stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def check_article_overlap(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]) -> int:
    train_keys = {clean_text(row.get("article_key")) for row in train_rows if clean_text(row.get("article_key"))}
    test_keys = {clean_text(row.get("article_key")) for row in test_rows if clean_text(row.get("article_key"))}
    return len(train_keys & test_keys)


def prediction_rows(model_name: str, fold_idx: int, test_rows: list[dict[str, Any]], y_pred: list[int]) -> list[dict[str, Any]]:
    out = []
    for row, pred in zip(test_rows, y_pred):
        gold = int(row.get("binary_label"))
        out.append({
            "model": model_name,
            "fold": fold_idx,
            "example_id": row.get("example_id"),
            "article_key": row.get("article_key"),
            "source_code": row.get("source_code"),
            "article_number": row.get("article_number"),
            "pattern": row.get("pattern"),
            "manual_label": row.get("manual_label"),
            "gold_label": gold,
            "pred_label": int(pred),
            "correct": gold == int(pred),
            "gold_label_name": row.get("label"),
            "candidate_term": row.get("candidate_term"),
            "candidate_definition": row.get("candidate_definition"),
            "raw_body": row.get("raw_body"),
            "input_text": clean_text(row.get("input_text")),
        })
    return out


def main() -> int:
    rows = load_jsonl(INPUT_FILE)
    folds = make_stratified_group_folds(rows, n_folds=N_FOLDS, seed=RANDOM_SEED)

    print(f"Input: {INPUT_FILE}")
    print(f"Total examples: {len(rows)}")
    print(f"Global labels: {dict(Counter(int(r.get('binary_label')) for r in rows))}")
    print(f"Folds: {N_FOLDS}")
    for i, fold in enumerate(folds, start=1):
        print(f"- fold {i}: n={len(fold)}, labels={dict(Counter(int(r.get('binary_label')) for r in fold))}")

    all_metrics: dict[str, Any] = {
        "task": "candidate_validation",
        "input_file": str(INPUT_FILE),
        "n_folds": N_FOLDS,
        "random_seed": RANDOM_SEED,
        "label_mapping": {"0": "invalid", "1": "accepted"},
        "models": {},
        "notes": [
            "5-fold cross-validation is grouped by article_key to reduce leakage.",
            "Accepted means valid_definition or partial.",
            "Invalid means manually rejected candidate.",
            "Report mean and standard deviation across folds.",
        ],
    }

    all_prediction_rows = []

    for model_name in make_models().keys():
        print()
        print(f"Cross-validating {model_name}...")
        fold_metrics = []

        for fold_idx in range(N_FOLDS):
            test_rows = folds[fold_idx]
            train_rows = [row for j, fold_rows in enumerate(folds) if j != fold_idx for row in fold_rows]
            overlap = check_article_overlap(train_rows, test_rows)

            x_train, y_train = rows_to_xy(train_rows)
            x_test, y_test = rows_to_xy(test_rows)

            model = make_models()[model_name]
            model.fit(x_train, y_train)
            y_pred = model.predict(x_test)

            metrics = evaluate_predictions(y_test, y_pred)
            metrics["fold"] = fold_idx + 1
            metrics["train_size"] = len(train_rows)
            metrics["test_size"] = len(test_rows)
            metrics["train_label_distribution"] = dict(Counter(y_train))
            metrics["test_label_distribution"] = dict(Counter(y_test))
            metrics["article_key_overlap_train_test"] = overlap

            fold_metrics.append(metrics)
            all_prediction_rows.extend(prediction_rows(model_name, fold_idx + 1, test_rows, y_pred))

            print(
                f"  fold {fold_idx + 1}: "
                f"macro-F1={metrics['macro_f1']:.3f}, "
                f"accepted-F1={metrics['accepted_f1']:.3f}, "
                f"invalid-F1={metrics['invalid_f1']:.3f}, "
                f"overlap={overlap}, "
                f"cm={metrics['confusion_matrix']}"
            )

        aggregate = {
            "accuracy": summarize([m["accuracy"] for m in fold_metrics]),
            "macro_f1": summarize([m["macro_f1"] for m in fold_metrics]),
            "accepted_f1": summarize([m["accepted_f1"] for m in fold_metrics]),
            "invalid_f1": summarize([m["invalid_f1"] for m in fold_metrics]),
            "invalid_precision": summarize([m["labels"]["0_invalid"]["precision"] for m in fold_metrics]),
            "invalid_recall": summarize([m["labels"]["0_invalid"]["recall"] for m in fold_metrics]),
            "accepted_precision": summarize([m["labels"]["1_accepted"]["precision"] for m in fold_metrics]),
            "accepted_recall": summarize([m["labels"]["1_accepted"]["recall"] for m in fold_metrics]),
        }

        all_metrics["models"][model_name] = {"folds": fold_metrics, "aggregate": aggregate}

        print(
            f"  aggregate: "
            f"macro-F1={aggregate['macro_f1']['mean']:.3f} ± {aggregate['macro_f1']['std']:.3f}, "
            f"accepted-F1={aggregate['accepted_f1']['mean']:.3f} ± {aggregate['accepted_f1']['std']:.3f}, "
            f"invalid-F1={aggregate['invalid_f1']['mean']:.3f} ± {aggregate['invalid_f1']['std']:.3f}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METRICS.write_text(json.dumps(all_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(OUTPUT_PREDICTIONS, all_prediction_rows)

    print()
    print(f"Wrote metrics: {OUTPUT_METRICS}")
    print(f"Wrote predictions: {OUTPUT_PREDICTIONS}")

    print()
    print("Best model by mean macro-F1:")
    best_name, best_values = sorted(
        all_metrics["models"].items(),
        key=lambda item: item[1]["aggregate"]["macro_f1"]["mean"],
        reverse=True,
    )[0]
    agg = best_values["aggregate"]
    print(
        f"- {best_name}: "
        f"macro-F1={agg['macro_f1']['mean']:.3f} ± {agg['macro_f1']['std']:.3f}, "
        f"accepted-F1={agg['accepted_f1']['mean']:.3f} ± {agg['accepted_f1']['std']:.3f}, "
        f"invalid-F1={agg['invalid_f1']['mean']:.3f} ± {agg['invalid_f1']['std']:.3f}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
