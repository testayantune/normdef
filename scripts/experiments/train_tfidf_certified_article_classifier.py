#!/usr/bin/env python3
"""
TF-IDF baselines for NormDef-FR v0.6 certified article-level definition detection.

Task:
    Given an article text, predict whether it is:
        1 = definition_article
        0 = certified_true_negative

Inputs:
    data/experiments/v0_6/certified_article_classification/splits/train.jsonl
    data/experiments/v0_6/certified_article_classification/splits/dev.jsonl
    data/experiments/v0_6/certified_article_classification/splits/test.jsonl

Outputs:
    data/experiments/v0_6/certified_article_classification/results/article_classification_certified_tfidf_metrics.json
    data/experiments/v0_6/certified_article_classification/results/article_classification_certified_tfidf_predictions.jsonl

Models:
    - TF-IDF word n-grams + Logistic Regression
    - TF-IDF word n-grams + Linear SVM
    - TF-IDF character n-grams + Linear SVM

Usage:
    python scripts/train_tfidf_certified_article_classifier.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "certified_article_classification"
SPLIT_DIR = BASE_DIR / "splits"

TRAIN_FILE = SPLIT_DIR / "train.jsonl"
DEV_FILE = SPLIT_DIR / "dev.jsonl"
TEST_FILE = SPLIT_DIR / "test.jsonl"

OUTPUT_DIR = BASE_DIR / "results"
OUTPUT_METRICS = OUTPUT_DIR / "article_classification_certified_tfidf_metrics.json"
OUTPUT_PREDICTIONS = OUTPUT_DIR / "article_classification_certified_tfidf_predictions.jsonl"


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
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=2,
                        max_df=0.95,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=2026,
                    ),
                ),
            ]
        ),
        "tfidf_word_linear_svm": Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=2,
                        max_df=0.95,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LinearSVC(
                        class_weight="balanced",
                        random_state=2026,
                    ),
                ),
            ]
        ),
        "tfidf_char_linear_svm": Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(3, 5),
                        min_df=2,
                        max_df=0.95,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LinearSVC(
                        class_weight="balanced",
                        random_state=2026,
                    ),
                ),
            ]
        ),
    }


def evaluate_model(model: Pipeline, x: list[str], y: list[int]) -> dict[str, Any]:
    pred = model.predict(x)

    precision, recall, f1, support = precision_recall_fscore_support(
        y,
        pred,
        labels=[0, 1],
        zero_division=0,
    )

    return {
        "accuracy": accuracy_score(y, pred),
        "macro_f1": f1_score(y, pred, average="macro", zero_division=0),
        "definition_f1": f1_score(y, pred, pos_label=1, zero_division=0),
        "true_negative_f1": f1_score(y, pred, pos_label=0, zero_division=0),
        "labels": {
            "0_certified_true_negative": {
                "precision": precision[0],
                "recall": recall[0],
                "f1": f1[0],
                "support": int(support[0]),
            },
            "1_definition_article": {
                "precision": precision[1],
                "recall": recall[1],
                "f1": f1[1],
                "support": int(support[1]),
            },
        },
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y,
            pred,
            labels=[0, 1],
            target_names=["certified_true_negative", "definition_article"],
            zero_division=0,
            output_dict=True,
        ),
    }


def prediction_rows(
    model_name: str,
    split_name: str,
    rows: list[dict[str, Any]],
    predictions: list[int],
) -> list[dict[str, Any]]:
    out = []

    for row, pred in zip(rows, predictions):
        gold = int(row.get("binary_label"))

        out.append(
            {
                "model": model_name,
                "split": split_name,
                "example_id": row.get("example_id"),
                "article_key": row.get("article_key"),
                "source_code": row.get("source_code"),
                "article_number": row.get("article_number"),
                "article_id": row.get("article_id"),
                "origin": row.get("origin"),
                "certification": row.get("certification"),
                "gold_label": gold,
                "pred_label": int(pred),
                "correct": gold == int(pred),
                "gold_label_name": row.get("label"),
                "input_text": clean_text(row.get("input_text")),
            }
        )

    return out


def main() -> int:
    train_rows = load_jsonl(TRAIN_FILE)
    dev_rows = load_jsonl(DEV_FILE)
    test_rows = load_jsonl(TEST_FILE)

    x_train, y_train = rows_to_xy(train_rows)
    x_dev, y_dev = rows_to_xy(dev_rows)
    x_test, y_test = rows_to_xy(test_rows)

    print(f"Train: {len(train_rows)} | labels: {dict(Counter(y_train))}")
    print(f"Dev:   {len(dev_rows)} | labels: {dict(Counter(y_dev))}")
    print(f"Test:  {len(test_rows)} | labels: {dict(Counter(y_test))}")

    models = make_models()

    all_metrics: dict[str, Any] = {
        "task": "article_definition_detection_certified",
        "train_file": str(TRAIN_FILE),
        "dev_file": str(DEV_FILE),
        "test_file": str(TEST_FILE),
        "label_mapping": {
            "0": "certified_true_negative",
            "1": "definition_article",
        },
        "dataset_sizes": {
            "train": len(train_rows),
            "dev": len(dev_rows),
            "test": len(test_rows),
        },
        "label_distribution": {
            "train": dict(Counter(y_train)),
            "dev": dict(Counter(y_dev)),
            "test": dict(Counter(y_test)),
        },
        "models": {},
        "notes": [
            "This certified setting replaces weak negatives with certified true negatives.",
            "Splits are balanced and grouped by article_key.",
            "Report this separately from the weak-negative article detection experiment.",
        ],
    }

    all_prediction_rows = []

    for model_name, model in models.items():
        print()
        print(f"Training {model_name}...")

        model.fit(x_train, y_train)

        dev_metrics = evaluate_model(model, x_dev, y_dev)
        test_metrics = evaluate_model(model, x_test, y_test)

        all_metrics["models"][model_name] = {
            "dev": dev_metrics,
            "test": test_metrics,
        }

        dev_pred = model.predict(x_dev)
        test_pred = model.predict(x_test)

        all_prediction_rows.extend(prediction_rows(model_name, "dev", dev_rows, dev_pred))
        all_prediction_rows.extend(prediction_rows(model_name, "test", test_rows, test_pred))

        print(
            f"Dev  macro-F1: {dev_metrics['macro_f1']:.3f} | "
            f"definition-F1: {dev_metrics['definition_f1']:.3f} | "
            f"true-negative-F1: {dev_metrics['true_negative_f1']:.3f}"
        )
        print(
            f"Test macro-F1: {test_metrics['macro_f1']:.3f} | "
            f"definition-F1: {test_metrics['definition_f1']:.3f} | "
            f"true-negative-F1: {test_metrics['true_negative_f1']:.3f}"
        )
        print(
            "Test confusion matrix [[TN_true_negative, FP_true_negative_to_definition], "
            f"[FN_definition_to_true_negative, TP_definition]]: {test_metrics['confusion_matrix']}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METRICS.write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_jsonl(OUTPUT_PREDICTIONS, all_prediction_rows)

    print()
    print(f"Wrote metrics: {OUTPUT_METRICS}")
    print(f"Wrote predictions: {OUTPUT_PREDICTIONS}")

    print()
    print("Best model on test by macro-F1:")
    best = sorted(
        all_metrics["models"].items(),
        key=lambda item: item[1]["test"]["macro_f1"],
        reverse=True,
    )[0]
    print(
        f"- {best[0]}: "
        f"macro-F1={best[1]['test']['macro_f1']:.3f}, "
        f"definition-F1={best[1]['test']['definition_f1']:.3f}, "
        f"true-negative-F1={best[1]['test']['true_negative_f1']:.3f}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
