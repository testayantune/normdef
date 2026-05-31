#!/usr/bin/env python3
"""
Error analysis for NormDef-FR v0.6 candidate validation.

Input:
    data/experiments/v0_6/results/candidate_validation_tfidf_predictions.jsonl

Outputs:
    data/experiments/v0_6/results/candidate_validation_error_analysis.json
    data/experiments/v0_6/results/candidate_validation_errors_for_review.jsonl
    data/experiments/v0_6/results/candidate_validation_false_positives.jsonl
    data/experiments/v0_6/results/candidate_validation_false_negatives.jsonl

Usage:
    python scripts/error_analysis_candidate_validation.py

Default:
    Analyze the best TF-IDF baseline selected previously:
        tfidf_word_logreg
        split = test
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PREDICTIONS = (
    PROJECT_ROOT
    / "data"
    / "experiments"
    / "v0_6"
    / "results"
    / "candidate_validation_tfidf_predictions.jsonl"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "results"

OUTPUT_SUMMARY = OUTPUT_DIR / "candidate_validation_error_analysis.json"
OUTPUT_ERRORS = OUTPUT_DIR / "candidate_validation_errors_for_review.jsonl"
OUTPUT_FALSE_POSITIVES = OUTPUT_DIR / "candidate_validation_false_positives.jsonl"
OUTPUT_FALSE_NEGATIVES = OUTPUT_DIR / "candidate_validation_false_negatives.jsonl"

MODEL_NAME = "tfidf_word_logreg"
SPLIT = "test"


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

    rows = []

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


def short_text(value: Any, max_len: int = 500) -> str:
    text = clean_text(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def error_type(row: dict[str, Any]) -> str:
    gold = int(row.get("gold_label"))
    pred = int(row.get("pred_label"))

    if gold == 0 and pred == 1:
        return "false_positive_invalid_predicted_accepted"

    if gold == 1 and pred == 0:
        return "false_negative_accepted_predicted_invalid"

    return "correct"


def make_review_row(row: dict[str, Any]) -> dict[str, Any]:
    etype = error_type(row)

    return {
        "error_type": etype,
        "model": row.get("model"),
        "split": row.get("split"),
        "example_id": row.get("example_id"),
        "source_code": row.get("source_code"),
        "article_number": row.get("article_number"),
        "pattern": row.get("pattern"),
        "manual_label": row.get("manual_label"),
        "gold_label": row.get("gold_label"),
        "pred_label": row.get("pred_label"),
        "candidate_term": row.get("candidate_term"),
        "candidate_definition": row.get("candidate_definition"),
        "raw_body": row.get("raw_body"),
        "input_text_short": short_text(row.get("input_text")),
        "diagnostic_hint": diagnostic_hint(row),
    }


def diagnostic_hint(row: dict[str, Any]) -> str:
    """
    Very simple heuristic hints to speed up qualitative review.
    """
    etype = error_type(row)
    pattern = clean_text(row.get("pattern")).lower()
    term = clean_text(row.get("candidate_term"))
    definition = clean_text(row.get("candidate_definition"))
    raw_body = clean_text(row.get("raw_body"))

    hints = []

    if etype == "false_positive_invalid_predicted_accepted":
        hints.append("Le modèle a conservé un candidat annoté invalid.")

        if pattern == "terme_colon_definition":
            hints.append("Vérifier si le deux-points introduit une liste, un intitulé, une condition ou un segment non définitionnel.")

        if len(definition.split()) < 4:
            hints.append("Définition très courte : risque de fragment incomplet.")

        if term and term.lower() not in raw_body.lower():
            hints.append("Le terme candidat n'apparaît pas littéralement dans le contexte.")

    elif etype == "false_negative_accepted_predicted_invalid":
        hints.append("Le modèle a rejeté un candidat pourtant accepté.")

        if clean_text(row.get("manual_label")) == "partial":
            hints.append("Le gold est partial : cas probablement ambigu pour le modèle.")

        if pattern in {"s'entend de", "on entend par"}:
            hints.append("Pattern canonique accepté mais possiblement avec frontières atypiques.")

        if len(definition.split()) > 40:
            hints.append("Définition longue : le modèle peut confondre définition et développement normatif.")

    return " ".join(hints)


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(clean_text(row.get(field)) or "unknown" for row in rows).most_common())


def main() -> int:
    rows = load_jsonl(INPUT_PREDICTIONS)

    selected = [
        row
        for row in rows
        if row.get("model") == MODEL_NAME and row.get("split") == SPLIT
    ]

    if not selected:
        raise RuntimeError(f"No rows found for model={MODEL_NAME!r}, split={SPLIT!r}")

    errors = [row for row in selected if not bool(row.get("correct"))]
    false_positives = [row for row in errors if error_type(row) == "false_positive_invalid_predicted_accepted"]
    false_negatives = [row for row in errors if error_type(row) == "false_negative_accepted_predicted_invalid"]

    review_errors = [make_review_row(row) for row in errors]
    review_fps = [make_review_row(row) for row in false_positives]
    review_fns = [make_review_row(row) for row in false_negatives]

    summary = {
        "model": MODEL_NAME,
        "split": SPLIT,
        "input_predictions": str(INPUT_PREDICTIONS),
        "counts": {
            "selected_predictions": len(selected),
            "errors_total": len(errors),
            "false_positives_invalid_predicted_accepted": len(false_positives),
            "false_negatives_accepted_predicted_invalid": len(false_negatives),
            "correct": len(selected) - len(errors),
        },
        "error_rate": len(errors) / len(selected) if selected else None,
        "false_positive_distribution": {
            "pattern": distribution(false_positives, "pattern"),
            "source_code": distribution(false_positives, "source_code"),
            "manual_label": distribution(false_positives, "manual_label"),
        },
        "false_negative_distribution": {
            "pattern": distribution(false_negatives, "pattern"),
            "source_code": distribution(false_negatives, "source_code"),
            "manual_label": distribution(false_negatives, "manual_label"),
        },
        "all_error_distribution": {
            "pattern": distribution(errors, "pattern"),
            "source_code": distribution(errors, "source_code"),
            "manual_label": distribution(errors, "manual_label"),
        },
        "interpretation_notes": [
            "False positives are invalid candidates predicted as accepted; they are dangerous because they would add noise to an automatically expanded dataset.",
            "False negatives are accepted candidates predicted as invalid; they reduce recall but are less harmful for high-precision dataset construction.",
            "Manual qualitative review should prioritize false positives.",
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_jsonl(OUTPUT_ERRORS, review_errors)
    write_jsonl(OUTPUT_FALSE_POSITIVES, review_fps)
    write_jsonl(OUTPUT_FALSE_NEGATIVES, review_fns)

    print(f"Input predictions: {INPUT_PREDICTIONS}")
    print(f"Model analyzed: {MODEL_NAME}")
    print(f"Split analyzed: {SPLIT}")
    print()
    print(f"Selected predictions: {len(selected)}")
    print(f"Errors total: {len(errors)}")
    print(f"- False positives invalid→accepted: {len(false_positives)}")
    print(f"- False negatives accepted→invalid: {len(false_negatives)}")
    print()
    print("False positive patterns:")
    for pattern, count in distribution(false_positives, "pattern").items():
        print(f"- {pattern}: {count}")

    print()
    print("False negative patterns:")
    for pattern, count in distribution(false_negatives, "pattern").items():
        print(f"- {pattern}: {count}")

    print()
    print(f"Wrote summary: {OUTPUT_SUMMARY}")
    print(f"Wrote errors for review: {OUTPUT_ERRORS}")
    print(f"Wrote false positives: {OUTPUT_FALSE_POSITIVES}")
    print(f"Wrote false negatives: {OUTPUT_FALSE_NEGATIVES}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
