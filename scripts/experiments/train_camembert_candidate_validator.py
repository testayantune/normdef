#!/usr/bin/env python3
"""
CamemBERT baseline for NormDef-FR v0.6 candidate validation.

Compatible version:
    This script adapts TrainingArguments to the installed transformers version.
    It avoids failing on arguments such as evaluation_strategy / eval_strategy /
    overwrite_output_dir when they are not supported locally.

Task:
    1 = accepted  (valid_definition or partial)
    0 = invalid

Usage:
    python scripts/train_camembert_candidate_validator.py
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

SPLIT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "splits" / "candidate_validation"

TRAIN_FILE = SPLIT_DIR / "train.jsonl"
DEV_FILE = SPLIT_DIR / "dev.jsonl"
TEST_FILE = SPLIT_DIR / "test.jsonl"

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "results"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "models" / "camembert_candidate_validation"

OUTPUT_METRICS = OUTPUT_DIR / "candidate_validation_camembert_metrics.json"
OUTPUT_PREDICTIONS = OUTPUT_DIR / "candidate_validation_camembert_predictions.jsonl"

MODEL_NAME = "camembert-base"

RANDOM_SEED = 2026
MAX_LENGTH = 256
NUM_EPOCHS = 8
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


class CandidateValidationDataset(Dataset):
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
        "accepted_f1": f1_score(labels, preds, pos_label=1, zero_division=0),
        "invalid_f1": f1_score(labels, preds, pos_label=0, zero_division=0),
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
        "accepted_f1": f1_score(labels, preds, pos_label=1, zero_division=0),
        "invalid_f1": f1_score(labels, preds, pos_label=0, zero_division=0),
        "labels": {
            "0_invalid": {
                "precision": precision[0],
                "recall": recall[0],
                "f1": f1[0],
                "support": int(support[0]),
            },
            "1_accepted": {
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
            target_names=["invalid", "accepted"],
            zero_division=0,
            output_dict=True,
        ),
    }


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
                "pattern": row.get("pattern"),
                "manual_label": row.get("manual_label"),
                "gold_label": gold,
                "pred_label": int(pred),
                "correct": gold == int(pred),
                "prob_invalid": float(probs[0]),
                "prob_accepted": float(probs[1]),
                "gold_label_name": row.get("label"),
                "candidate_term": row.get("candidate_term"),
                "candidate_definition": row.get("candidate_definition"),
                "raw_body": row.get("raw_body"),
                "input_text": clean_text(row.get("input_text")),
            }
        )

    return out


def predict_with_probabilities(trainer: Trainer, dataset: CandidateValidationDataset) -> tuple[list[int], list[list[float]]]:
    pred_output = trainer.predict(dataset)
    logits = pred_output.predictions
    probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()
    preds = np.argmax(probs, axis=-1)
    return preds.tolist(), probs.tolist()


def make_training_args() -> TrainingArguments:
    """
    Build TrainingArguments in a way that works across different transformers versions.
    Some installed versions accept evaluation_strategy; others accept eval_strategy;
    older versions may accept neither.
    """
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

    # Evaluation strategy naming changed across versions.
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

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_dataset = CandidateValidationDataset(train_rows, tokenizer, MAX_LENGTH)
    dev_dataset = CandidateValidationDataset(dev_rows, tokenizer, MAX_LENGTH)
    test_dataset = CandidateValidationDataset(test_rows, tokenizer, MAX_LENGTH)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label={0: "invalid", 1: "accepted"},
        label2id={"invalid": 0, "accepted": 1},
    )

    training_args = make_training_args()

    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_dataset,
        "eval_dataset": dev_dataset,
        "compute_metrics": compute_metrics,
    }

    # Transformers versions differ: recent versions use processing_class instead
    # of tokenizer, older ones use tokenizer, and some minimal installs accept neither.
    trainer_supported = set(inspect.signature(Trainer.__init__).parameters)
    if "tokenizer" in trainer_supported:
        trainer_kwargs["tokenizer"] = tokenizer
    elif "processing_class" in trainer_supported:
        trainer_kwargs["processing_class"] = tokenizer

    trainer_kwargs = {k: v for k, v in trainer_kwargs.items() if k in trainer_supported}

    print("Trainer arguments used:")
    for key in sorted(trainer_kwargs):
        if key in {"model", "args", "train_dataset", "eval_dataset", "compute_metrics", "tokenizer", "processing_class"}:
            print(f"- {key}")

    trainer = Trainer(**trainer_kwargs)

    trainer.train()

    dev_preds, dev_probs = predict_with_probabilities(trainer, dev_dataset)
    test_preds, test_probs = predict_with_probabilities(trainer, test_dataset)

    dev_labels = [int(row.get("binary_label")) for row in dev_rows]
    test_labels = [int(row.get("binary_label")) for row in test_rows]

    dev_metrics = detailed_metrics(dev_labels, dev_preds)
    test_metrics = detailed_metrics(test_labels, test_preds)

    metrics = {
        "task": "candidate_validation",
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
            "Accepted means valid_definition or partial.",
            "Invalid means manually rejected candidate.",
            "The test split is small and imbalanced; macro-F1 and invalid-F1 should be reported.",
            "TrainingArguments were filtered dynamically for local transformers compatibility.",
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
    print("CamemBERT candidate validation results")
    print(f"Dev  macro-F1: {dev_metrics['macro_f1']:.3f} | accepted-F1: {dev_metrics['accepted_f1']:.3f} | invalid-F1: {dev_metrics['invalid_f1']:.3f}")
    print(f"Test macro-F1: {test_metrics['macro_f1']:.3f} | accepted-F1: {test_metrics['accepted_f1']:.3f} | invalid-F1: {test_metrics['invalid_f1']:.3f}")
    print(f"Test confusion matrix [[TN_invalid, FP_invalid_to_accepted], [FN_accepted_to_invalid, TP_accepted]]: {test_metrics['confusion_matrix']}")
    print()
    print(f"Wrote metrics: {OUTPUT_METRICS}")
    print(f"Wrote predictions: {OUTPUT_PREDICTIONS}")
    print(f"Saved model: {save_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
