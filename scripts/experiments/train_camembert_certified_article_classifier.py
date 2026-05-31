#!/usr/bin/env python3
"""
CamemBERT baseline for NormDef-FR v0.6 certified article-level definition detection.

Task:
    Given an article text, predict whether it is:
        1 = definition_article
        0 = certified_true_negative

Inputs:
    data/experiments/v0_6/certified_article_classification/splits/train.jsonl
    data/experiments/v0_6/certified_article_classification/splits/dev.jsonl
    data/experiments/v0_6/certified_article_classification/splits/test.jsonl

Outputs:
    data/experiments/v0_6/certified_article_classification/results/article_classification_certified_camembert_metrics.json
    data/experiments/v0_6/certified_article_classification/results/article_classification_certified_camembert_predictions.jsonl
    data/experiments/v0_6/certified_article_classification/models/camembert_article_classification/best_model/

Usage:
    python scripts/train_camembert_certified_article_classifier.py

Notes:
    This script is compatible with multiple transformers versions.
"""

from __future__ import annotations

import inspect
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "certified_article_classification"
SPLIT_DIR = BASE_DIR / "splits"

TRAIN_FILE = SPLIT_DIR / "train.jsonl"
DEV_FILE = SPLIT_DIR / "dev.jsonl"
TEST_FILE = SPLIT_DIR / "test.jsonl"

OUTPUT_DIR = BASE_DIR / "results"
MODEL_OUTPUT_DIR = BASE_DIR / "models" / "camembert_article_classification"

OUTPUT_METRICS = OUTPUT_DIR / "article_classification_certified_camembert_metrics.json"
OUTPUT_PREDICTIONS = OUTPUT_DIR / "article_classification_certified_camembert_predictions.jsonl"

MODEL_NAME = "camembert-base"

RANDOM_SEED = 2026
MAX_LENGTH = 256
NUM_EPOCHS = 5
LEARNING_RATE = 2e-5
TRAIN_BATCH_SIZE = 8
EVAL_BATCH_SIZE = 16
WEIGHT_DECAY = 0.01


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


class ArticleClassificationDataset(Dataset):
    def __init__(self, rows: list[dict[str, Any]], tokenizer: AutoTokenizer, max_length: int):
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        row = self.rows[idx]
        text = clean_text(row.get("input_text"))
        label = int(row.get("binary_label"))

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(label, dtype=torch.long)
        return item


def compute_metrics(eval_pred) -> dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)

    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        "definition_f1": f1_score(labels, preds, pos_label=1, zero_division=0),
        "true_negative_f1": f1_score(labels, preds, pos_label=0, zero_division=0),
    }


def detailed_metrics(labels: list[int], preds: list[int]) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        preds,
        labels=[0, 1],
        zero_division=0,
    )

    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        "definition_f1": f1_score(labels, preds, pos_label=1, zero_division=0),
        "true_negative_f1": f1_score(labels, preds, pos_label=0, zero_division=0),
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
        "confusion_matrix": confusion_matrix(labels, preds, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            labels,
            preds,
            labels=[0, 1],
            target_names=["certified_true_negative", "definition_article"],
            zero_division=0,
            output_dict=True,
        ),
    }


def predict_with_probabilities(trainer: Trainer, dataset: ArticleClassificationDataset) -> tuple[list[int], list[list[float]]]:
    pred_output = trainer.predict(dataset)
    logits = pred_output.predictions
    probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()
    preds = np.argmax(probs, axis=-1)
    return preds.tolist(), probs.tolist()


def prediction_rows(
    split_name: str,
    rows: list[dict[str, Any]],
    preds: list[int],
    probabilities: list[list[float]],
) -> list[dict[str, Any]]:
    out = []

    for row, pred, probs in zip(rows, preds, probabilities):
        gold = int(row.get("binary_label"))
        out.append(
            {
                "model": MODEL_NAME,
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
                "prob_true_negative": float(probs[0]),
                "prob_definition": float(probs[1]),
                "gold_label_name": row.get("label"),
                "input_text": clean_text(row.get("input_text")),
            }
        )
    return out


def make_training_args() -> TrainingArguments:
    supported = set(inspect.signature(TrainingArguments.__init__).parameters)

    kwargs: dict[str, Any] = {
        "output_dir": str(MODEL_OUTPUT_DIR),
        "num_train_epochs": NUM_EPOCHS,
        "learning_rate": LEARNING_RATE,
        "per_device_train_batch_size": TRAIN_BATCH_SIZE,
        "per_device_eval_batch_size": EVAL_BATCH_SIZE,
        "weight_decay": WEIGHT_DECAY,
        "logging_dir": str(MODEL_OUTPUT_DIR / "logs"),
        "logging_steps": 10,
        "seed": RANDOM_SEED,
        "do_train": True,
        "do_eval": True,
    }

    if "evaluation_strategy" in supported:
        kwargs["evaluation_strategy"] = "epoch"
    elif "eval_strategy" in supported:
        kwargs["eval_strategy"] = "epoch"

    if "save_strategy" in supported:
        kwargs["save_strategy"] = "epoch"

    if "save_total_limit" in supported:
        kwargs["save_total_limit"] = 2

    if "load_best_model_at_end" in supported and ("evaluation_strategy" in kwargs or "eval_strategy" in kwargs):
        kwargs["load_best_model_at_end"] = True

    if "metric_for_best_model" in supported and "load_best_model_at_end" in kwargs:
        kwargs["metric_for_best_model"] = "macro_f1"

    if "greater_is_better" in supported and "load_best_model_at_end" in kwargs:
        kwargs["greater_is_better"] = True

    if "report_to" in supported:
        kwargs["report_to"] = []

    filtered = {k: v for k, v in kwargs.items() if k in supported}

    print("TrainingArguments used:")
    for key in sorted(filtered):
        print(f"- {key}: {filtered[key]}")

    return TrainingArguments(**filtered)


def make_trainer(
    model: AutoModelForSequenceClassification,
    training_args: TrainingArguments,
    train_dataset: ArticleClassificationDataset,
    dev_dataset: ArticleClassificationDataset,
    tokenizer: AutoTokenizer,
) -> Trainer:
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_dataset,
        "eval_dataset": dev_dataset,
        "compute_metrics": compute_metrics,
    }

    trainer_supported = set(inspect.signature(Trainer.__init__).parameters)

    if "tokenizer" in trainer_supported:
        trainer_kwargs["tokenizer"] = tokenizer
    elif "processing_class" in trainer_supported:
        trainer_kwargs["processing_class"] = tokenizer

    trainer_kwargs = {k: v for k, v in trainer_kwargs.items() if k in trainer_supported}

    print("Trainer arguments used:")
    for key in sorted(trainer_kwargs):
        print(f"- {key}")

    return Trainer(**trainer_kwargs)


def main() -> int:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)
    set_seed(RANDOM_SEED)

    train_rows = load_jsonl(TRAIN_FILE)
    dev_rows = load_jsonl(DEV_FILE)
    test_rows = load_jsonl(TEST_FILE)

    print(f"Train: {len(train_rows)}")
    print(f"Dev:   {len(dev_rows)}")
    print(f"Test:  {len(test_rows)}")
    print(f"Model: {MODEL_NAME}")
    print(f"Epochs: {NUM_EPOCHS}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_dataset = ArticleClassificationDataset(train_rows, tokenizer, MAX_LENGTH)
    dev_dataset = ArticleClassificationDataset(dev_rows, tokenizer, MAX_LENGTH)
    test_dataset = ArticleClassificationDataset(test_rows, tokenizer, MAX_LENGTH)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label={0: "certified_true_negative", 1: "definition_article"},
        label2id={"certified_true_negative": 0, "definition_article": 1},
    )

    training_args = make_training_args()

    trainer = make_trainer(
        model=model,
        training_args=training_args,
        train_dataset=train_dataset,
        dev_dataset=dev_dataset,
        tokenizer=tokenizer,
    )

    trainer.train()

    dev_preds, dev_probs = predict_with_probabilities(trainer, dev_dataset)
    test_preds, test_probs = predict_with_probabilities(trainer, test_dataset)

    dev_labels = [int(row.get("binary_label")) for row in dev_rows]
    test_labels = [int(row.get("binary_label")) for row in test_rows]

    dev_metrics = detailed_metrics(dev_labels, dev_preds)
    test_metrics = detailed_metrics(test_labels, test_preds)

    metrics = {
        "task": "article_definition_detection_certified",
        "model": MODEL_NAME,
        "train_file": str(TRAIN_FILE),
        "dev_file": str(DEV_FILE),
        "test_file": str(TEST_FILE),
        "model_output_dir": str(MODEL_OUTPUT_DIR),
        "hyperparameters": {
            "max_length": MAX_LENGTH,
            "num_epochs": NUM_EPOCHS,
            "learning_rate": LEARNING_RATE,
            "train_batch_size": TRAIN_BATCH_SIZE,
            "eval_batch_size": EVAL_BATCH_SIZE,
            "weight_decay": WEIGHT_DECAY,
            "random_seed": RANDOM_SEED,
        },
        "dev": dev_metrics,
        "test": test_metrics,
        "notes": [
            "Certified setting: positives are gold definition-bearing articles; negatives are certified true negatives.",
            "Dataset is balanced and split by article_key.",
            "Report separately from the weak-negative article classification setting.",
        ],
    }

    all_predictions = []
    all_predictions.extend(prediction_rows("dev", dev_rows, dev_preds, dev_probs))
    all_predictions.extend(prediction_rows("test", test_rows, test_preds, test_probs))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(OUTPUT_PREDICTIONS, all_predictions)

    save_dir = MODEL_OUTPUT_DIR / "best_model"
    trainer.save_model(str(save_dir))
    tokenizer.save_pretrained(str(save_dir))

    print()
    print("CamemBERT certified article definition detection results")
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
    print()
    print(f"Wrote metrics: {OUTPUT_METRICS}")
    print(f"Wrote predictions: {OUTPUT_PREDICTIONS}")
    print(f"Saved model: {save_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
