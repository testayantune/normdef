#!/usr/bin/env python3
"""
Rule-based extraction baseline for NormDef-FR v0.6.

Task:
    Given raw_body, extract:
        - term
        - definition

Input:
    data/experiments/v0_6/splits/term_definition_extraction/test.jsonl

Outputs:
    data/experiments/v0_6/results/rule_based_extraction_predictions.jsonl
    data/experiments/v0_6/results/rule_based_extraction_metrics.json

Usage:
    python scripts/rule_based_extraction_baseline.py

Evaluation:
    - term exact match
    - definition exact match
    - both exact match
    - token-level F1 for term
    - token-level F1 for definition
    - metrics by pattern group

This baseline is intentionally simple and transparent.
It is not meant to reproduce all annotation corrections, but to provide a
scientifically interpretable baseline for the paper.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_TEST = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "splits" / "term_definition_extraction" / "test.jsonl"

OUTPUT_DIR = PROJECT_ROOT / "data" / "experiments" / "v0_6" / "results"
OUTPUT_PREDICTIONS = OUTPUT_DIR / "rule_based_extraction_predictions.jsonl"
OUTPUT_METRICS = OUTPUT_DIR / "rule_based_extraction_metrics.json"


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    text = text.replace("\xa0", " ")
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_for_match(value: Any) -> str:
    text = clean_text(value).lower()
    text = strip_accents(text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .;:,\"'")
    return text


def tokenize(value: Any) -> list[str]:
    text = normalize_for_match(value)
    if not text:
        return []
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text)


def token_f1(pred: str, gold: str) -> float:
    pred_tokens = tokenize(pred)
    gold_tokens = tokenize(gold)

    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0

    pred_counter = Counter(pred_tokens)
    gold_counter = Counter(gold_tokens)
    overlap = sum((pred_counter & gold_counter).values())

    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)

    return 2 * precision * recall / (precision + recall)


def exact_match(pred: str, gold: str) -> bool:
    return normalize_for_match(pred) == normalize_for_match(gold)


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


def trim_definition(value: str) -> str:
    """
    Trim obvious trailing noise while keeping legal references.
    """
    text = clean_text(value)

    # Stop before common continuation markers that often introduce non-definitional material.
    stop_patterns = [
        r"\s+Les\s+modalités\s+",
        r"\s+Un\s+décret\s+",
        r"\s+Un\s+arrêté\s+",
        r"\s+Ces\s+dispositions\s+",
        r"\s+Pour\s+l'application\s+du\s+présent\s+alinéa\s*,",
    ]

    for pattern in stop_patterns:
        m = re.search(pattern, text)
        if m and m.start() > 30:
            text = text[:m.start()].strip()

    return text.strip(" ;")


def extract_colon_definition(text: str) -> tuple[str, str, str] | None:
    """
    Pattern:
        Terme : définition
        1° Terme : définition
        a) Terme : définition
    """
    pattern = re.compile(
        r"^\s*(?:(?:\d+°(?:\s+bis|\s+ter)?|[a-z]\)|[IVXLC]+\.)\s*)?"
        r"(?P<term>[^:]{2,220}?)\s*:\s*(?P<definition>.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(text)
    if not m:
        return None

    term = clean_text(m.group("term"))
    definition = trim_definition(m.group("definition"))

    if not term or not definition:
        return None

    return term.strip(" \"“”"), definition, "colon_definition"


def extract_on_entend_par(text: str) -> tuple[str, str, str] | None:
    """
    Pattern:
        on entend par "terme" définition
        on entend par terme : définition
    """
    pattern = re.compile(
        r"(?:on\s+entend\s+par|sont\s+entendus\s+par)\s+"
        r"(?:[\"“](?P<term_q>[^\"”]{1,220})[\"”]|(?P<term>[^,:;\n]{1,220}?))"
        r"\s*(?:,|:)?\s+"
        r"(?P<definition>.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(text)
    if not m:
        return None

    term = clean_text(m.group("term_q") or m.group("term"))
    definition = trim_definition(m.group("definition"))

    if not term or not definition:
        return None

    return term.strip(" \"“”"), definition, "on_entend_par"


def extract_sentend_de(text: str) -> tuple[str, str, str] | None:
    """
    Pattern:
        terme s'entend de définition
        terme s'entendent de définition
    """
    pattern = re.compile(
        r"(?P<term>.{1,220}?)\s+s['’]\s*entend(?:ent)?\s+de\s+(?P<definition>.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(text)
    if not m:
        return None

    term = clean_text(m.group("term"))
    definition = trim_definition(m.group("definition"))

    # Remove scope prefix if present.
    term = re.sub(
        r"^(?:pour\s+l'application\s+[^,]+,\s*)",
        "",
        term,
        flags=re.IGNORECASE,
    ).strip()

    if not term or not definition:
        return None

    return term.strip(" \"“”"), definition, "sentend_de"


def extract_defini_comme(text: str) -> tuple[str, str, str] | None:
    """
    Pattern:
        terme est défini comme définition
        terme défini comme définition
    """
    pattern = re.compile(
        r"(?P<term>.{1,220}?)\s+"
        r"(?:est\s+|sont\s+)?(?:défini|définie|définis|définies)\s+comme\s+"
        r"(?P<definition>.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(text)
    if not m:
        return None

    term = clean_text(m.group("term"))
    definition = trim_definition(m.group("definition"))

    if not term or not definition:
        return None

    return term.strip(" \"“”"), definition, "defini_comme"


def extract_qualification(text: str) -> tuple[str, str, str] | None:
    """
    Pattern:
        terme est considéré comme qualification si/lorsque définition
    """
    pattern = re.compile(
        r"(?P<subject>.{1,180}?)\s+"
        r"(?:est|sont)\s+considéré(?:e|s|es)?\s+comme\s+"
        r"(?P<term>.{1,160}?)\s+"
        r"(?:si|lorsque|quand|dès lors que)\s+"
        r"(?P<definition>.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(text)
    if not m:
        return None

    term = clean_text(m.group("term"))
    definition = trim_definition(m.group("definition"))

    if not term or not definition:
        return None

    return term.strip(" \"“”"), definition, "qualification"


def rule_based_extract(text: str) -> dict[str, Any]:
    text = clean_text(text)

    extractors = [
        extract_colon_definition,
        extract_on_entend_par,
        extract_sentend_de,
        extract_defini_comme,
        extract_qualification,
    ]

    for extractor in extractors:
        result = extractor(text)
        if result is not None:
            term, definition, rule = result
            return {
                "pred_term": term,
                "pred_definition": definition,
                "matched_rule": rule,
                "no_prediction": False,
            }

    return {
        "pred_term": "",
        "pred_definition": "",
        "matched_rule": None,
        "no_prediction": True,
    }


def coarse_pattern(pattern: Any) -> str:
    p = clean_text(pattern)

    if p == "terme_colon_definition":
        return "colon_definition"

    if "s'entend de" in p:
        return "sentend_de"

    if "on entend par" in p:
        return "on_entend_par"

    if "défini" in p or "defini" in p:
        return "defini_comme"

    if "considéré" in p or "considérés" in p:
        return "qualification"

    return "other"


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)

    if n == 0:
        return {}

    term_exact = sum(1 for r in rows if r["term_exact_match"])
    definition_exact = sum(1 for r in rows if r["definition_exact_match"])
    both_exact = sum(1 for r in rows if r["both_exact_match"])
    no_prediction = sum(1 for r in rows if r["no_prediction"])

    term_f1_values = [r["term_token_f1"] for r in rows]
    definition_f1_values = [r["definition_token_f1"] for r in rows]

    return {
        "n": n,
        "term_exact_match": term_exact / n,
        "definition_exact_match": definition_exact / n,
        "both_exact_match": both_exact / n,
        "term_token_f1": sum(term_f1_values) / n,
        "definition_token_f1": sum(definition_f1_values) / n,
        "no_prediction_rate": no_prediction / n,
    }


def main() -> int:
    rows = load_jsonl(INPUT_TEST)

    predictions = []

    for row in rows:
        input_text = clean_text(row.get("input_text"))
        gold_term = clean_text(row.get("target_term"))
        gold_definition = clean_text(row.get("target_definition"))

        pred = rule_based_extract(input_text)

        pred_term = pred["pred_term"]
        pred_definition = pred["pred_definition"]

        term_em = exact_match(pred_term, gold_term)
        definition_em = exact_match(pred_definition, gold_definition)

        out = {
            "example_id": row.get("example_id"),
            "source_code": row.get("source_code"),
            "article_number": row.get("article_number"),
            "article_id": row.get("article_id"),
            "pattern": row.get("pattern"),
            "coarse_pattern": coarse_pattern(row.get("pattern")),
            "input_text": input_text,
            "gold_term": gold_term,
            "gold_definition": gold_definition,
            "pred_term": pred_term,
            "pred_definition": pred_definition,
            "matched_rule": pred["matched_rule"],
            "no_prediction": pred["no_prediction"],
            "term_exact_match": term_em,
            "definition_exact_match": definition_em,
            "both_exact_match": term_em and definition_em,
            "term_token_f1": token_f1(pred_term, gold_term),
            "definition_token_f1": token_f1(pred_definition, gold_definition),
        }

        predictions.append(out)

    by_pattern: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in predictions:
        by_pattern[row["coarse_pattern"]].append(row)
        by_rule[str(row["matched_rule"] or "no_rule")].append(row)

    metrics = {
        "input_file": str(INPUT_TEST),
        "output_predictions": str(OUTPUT_PREDICTIONS),
        "overall": compute_metrics(predictions),
        "by_coarse_pattern": {
            pattern: compute_metrics(items)
            for pattern, items in sorted(by_pattern.items())
        },
        "by_matched_rule": {
            rule: compute_metrics(items)
            for rule, items in sorted(by_rule.items())
        },
        "counts": {
            "test_examples": len(predictions),
            "matched_rule_distribution": dict(Counter(str(r["matched_rule"] or "no_rule") for r in predictions).most_common()),
            "coarse_pattern_distribution": dict(Counter(r["coarse_pattern"] for r in predictions).most_common()),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT_PREDICTIONS, predictions)
    OUTPUT_METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    overall = metrics["overall"]

    print(f"Input test file: {INPUT_TEST}")
    print(f"Predictions: {OUTPUT_PREDICTIONS}")
    print(f"Metrics: {OUTPUT_METRICS}")
    print()
    print("Overall rule-based extraction baseline")
    print(f"- n: {overall['n']}")
    print(f"- term exact match:       {overall['term_exact_match']:.3f}")
    print(f"- definition exact match: {overall['definition_exact_match']:.3f}")
    print(f"- both exact match:       {overall['both_exact_match']:.3f}")
    print(f"- term token F1:          {overall['term_token_f1']:.3f}")
    print(f"- definition token F1:    {overall['definition_token_f1']:.3f}")
    print(f"- no prediction rate:     {overall['no_prediction_rate']:.3f}")

    print()
    print("By coarse pattern:")
    for pattern, values in metrics["by_coarse_pattern"].items():
        print(
            f"- {pattern}: n={values['n']}, "
            f"term EM={values['term_exact_match']:.3f}, "
            f"def EM={values['definition_exact_match']:.3f}, "
            f"term F1={values['term_token_f1']:.3f}, "
            f"def F1={values['definition_token_f1']:.3f}"
        )

    print()
    print("Matched rule distribution:")
    for rule, count in metrics["counts"]["matched_rule_distribution"].items():
        print(f"- {rule}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
