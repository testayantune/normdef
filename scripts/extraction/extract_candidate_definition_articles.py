#!/usr/bin/env python3
"""
Extract candidate definition articles from current LEGI code articles.

NormDef-FR version.

Input:
    data/processed/articles_current.jsonl

Output:
    data/candidates/candidate_definition_articles.jsonl

Usage:
    python scripts/extract_candidate_definition_articles.py

Expected input JSONL fields:
    - article_id
    - source_code
    - article_number
    - etat
    - date_debut
    - date_fin
    - text
    - source_file

The script preserves all input fields and adds:
    - matched_definition_patterns
    - matched_pattern_categories
    - candidate_score
    - noise_risk
    - text_preview

Methodological note:
    Patterns are separated into three categories:
    1. strong: high-confidence explicit definitional markers;
    2. medium: useful but context-dependent markers;
    3. high_noise: broad legal markers likely to produce false positives.

This distinction is important for later evaluation and for reporting precision
by pattern family in the paper.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_JSONL = PROJECT_ROOT / "data" / "processed" / "articles_current.jsonl"
OUTPUT_JSONL = PROJECT_ROOT / "data" / "candidates" / "candidate_definition_articles.jsonl"


# ---------------------------------------------------------------------------
# Pattern inventory
# ---------------------------------------------------------------------------

PATTERNS: dict[str, dict[str, str]] = {
    # -----------------------------------------------------------------------
    # STRONG PATTERNS
    # -----------------------------------------------------------------------
    "on entend par": {
        "regex": r"\bon entend par\b",
        "category": "strong",
    },
    "on désigne par": {
        "regex": r"\bon désigne par\b",
        "category": "strong",
    },
    "au sens du présent": {
        "regex": r"\bau sens du présent\b",
        "category": "strong",
    },
    "au sens de la présente": {
        "regex": r"\bau sens de la présente\b",
        "category": "strong",
    },
    "pour l'application du présent": {
        "regex": r"\bpour l['’]application du présent\b",
        "category": "strong",
    },
    "pour l'application de la présente": {
        "regex": r"\bpour l['’]application de la présente\b",
        "category": "strong",
    },
    "aux fins du présent": {
        "regex": r"\baux fins du présent\b",
        "category": "strong",
    },
    "aux fins de la présente": {
        "regex": r"\baux fins de la présente\b",
        "category": "strong",
    },

    # Scope extensions:
    # Examples:
    # "Au sens du présent livre..."
    # "Au sens de la présente section..."
    "au sens du présent étendu": {
        "regex": (
            r"\bau sens (?:"
            r"du présent (?:article|chapitre|titre|livre|code|décret|règlement|arrêté)"
            r"|de la présente (?:section|loi|ordonnance|directive|partie)"
            r")\b"
        ),
        "category": "strong",
    },

    # Quoted term after "on entend par".
    # Example: "On entend par « consommateur » ..."
    "guillemets_définition": {
        "regex": r"\bon entend par\s+[«\"][^»\"]{1,100}[»\"]",
        "category": "strong",
    },

    # -----------------------------------------------------------------------
    # DEFINED-AS AND QUALIFICATION PATTERNS
    # -----------------------------------------------------------------------
    "défini comme": {
        "regex": r"\bdéfini(?:e|s|es)? comme\b",
        "category": "strong",
    },
    "est défini": {
        "regex": r"\best défini(?:e)?\b",
        "category": "strong",
    },
    "sont définis": {
        "regex": r"\bsont défini(?:e)?s\b",
        "category": "strong",
    },
    "est entendu comme": {
        "regex": r"\best entendu(?:e|s|es)? comme\b",
        "category": "strong",
    },
    "se définit comme": {
        "regex": r"\bse défini(?:t|ssent) comme\b",
        "category": "strong",
    },

    # Qualification patterns.
    "est qualifié de": {
        "regex": r"\best qualifié(?:e)? de\b",
        "category": "strong",
    },
    "sont qualifiés de": {
        "regex": r"\bsont qualifié(?:e)?s de\b",
        "category": "strong",
    },
    "est considéré comme": {
        "regex": r"\best considéré(?:e)? comme\b",
        "category": "strong",
    },
    "sont considérés comme": {
        "regex": r"\bsont considéré(?:e)?s comme\b",
        "category": "strong",
    },
    "est regardé comme": {
        "regex": r"\best regardé(?:e|s|es)? comme\b",
        "category": "strong",
    },
    "est réputé": {
        "regex": r"\best réputé(?:e)?\b",
        "category": "medium",
    },
    "sont réputés": {
        "regex": r"\bsont réputé(?:e)?s\b",
        "category": "medium",
    },

    # -----------------------------------------------------------------------
    # FRENCH LEGAL VARIANTS
    # -----------------------------------------------------------------------
    # Example:
    # "Le terme X s'entend de..."
    # "Les mots X s'entendent comme..."
    "s'entend de": {
        "regex": r"\bs['’]entend(?:ent)?\s+(?:de|comme|par)\b",
        "category": "strong",
    },

    # External or generic scope references:
    # Example:
    # "au sens de l'article L. ..."
    # "au sens du règlement ..."
    # This can be definitional, but sometimes only references an external definition.
    "au sens de": {
        "regex": r"\bau sens de\s+(?:l['’]article|du règlement|de la directive|du code|de l['’]ordonnance)\b",
        "category": "medium",
    },

    # Inverted pattern:
    # Example:
    # "Par « services numériques », on entend..."
    "par terme on entend": {
        "regex": r"\bpar\s+[«\"][^»\"]{1,100}[»\"],?\s+on entend\b",
        "category": "strong",
    },

    # Alias-type formulations.
    # Frequent in legal drafting, but not always a true normative definition.
    "ci-après dénommé": {
        "regex": r"\bci[- ]après\s+(?:dénommé|désigné|appelé)(?:e|s|es)?\b",
        "category": "medium",
    },

    # Qualitative sense expressions.
    # Useful for analysis, but weaker for extraction.
    "au sens strict": {
        "regex": r"\bau sens\s+(?:strict|large|technique|juridique)\b",
        "category": "medium",
    },

    # -----------------------------------------------------------------------
    # COLON DEFINITIONS
    # -----------------------------------------------------------------------
    # Example:
    # "Consommateur : toute personne physique..."
    # "Déchet : toute substance..."
    "terme_colon_definition": {
        "regex": (
            r"(?:^|\n|;\s*)"
            r"\s*(?:\d+°\s*)?"
            r"[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ0-9'’\-\s]{2,100}"
            r"\s*:\s+"
            r"(?:un|une|des|du|de la|de l'|tout|toute|tous|toutes|la|le|les|l')\b"
        ),
        "category": "strong",
    },

    # -----------------------------------------------------------------------
    # HIGH-NOISE PATTERNS
    # -----------------------------------------------------------------------
    # These are kept, but flagged as high noise.
    # They should not be trusted as gold evidence without manual review.
    "désigne": {
        "regex": r"\bdésigne(?:nt)?\b",
        "category": "high_noise",
    },
    "constitue": {
        "regex": r"\bconstitue(?:nt)?\b",
        "category": "high_noise",
    },
    "vise": {
        "regex": r"\b(?:le présent article|la présente loi|le présent texte|la présente section)\s+vise(?:nt)?\b",
        "category": "high_noise",
    },
}


CATEGORY_SCORE = {
    "strong": 3,
    "medium": 2,
    "high_noise": 1,
}


def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Load a JSONL file line by line."""
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] Line {line_number}: invalid JSON: {exc}")
                continue

            if not isinstance(obj, dict):
                print(f"[WARN] Line {line_number}: expected JSON object")
                continue

            obj["__line_number"] = line_number
            yield obj


def find_matches(text: str) -> list[dict[str, str]]:
    """Return matched pattern labels and categories."""
    matches: list[dict[str, str]] = []

    for label, spec in PATTERNS.items():
        pattern = spec["regex"]
        category = spec["category"]

        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            matches.append(
                {
                    "label": label,
                    "category": category,
                }
            )

    return matches


def score_candidate(matches: list[dict[str, str]]) -> int:
    """Score candidates based on pattern category."""
    return sum(CATEGORY_SCORE.get(match["category"], 0) for match in matches)


def compute_noise_risk(matches: list[dict[str, str]]) -> str:
    """
    Assign a noise-risk label.

    low:
        at least one strong pattern.

    medium:
        no strong pattern, but at least one medium pattern.

    high:
        only high-noise patterns.
    """
    categories = {match["category"] for match in matches}

    if "strong" in categories:
        return "low"

    if "medium" in categories:
        return "medium"

    return "high"


def make_preview(text: str, max_length: int = 500) -> str:
    """Create a compact text preview for quick manual inspection."""
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."


def main() -> int:
    if not INPUT_JSONL.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_JSONL}\n"
            "Run scripts/filter_current_articles.py first."
        )

    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0
    skipped_empty_text = 0

    pattern_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    noise_counter: Counter[str] = Counter()
    source_code_counter: Counter[str] = Counter()

    with OUTPUT_JSONL.open("w", encoding="utf-8") as out:
        for article in load_jsonl(INPUT_JSONL):
            total += 1

            text = article.get("text") or article.get("raw_text") or ""
            if not isinstance(text, str) or not text.strip():
                skipped_empty_text += 1
                continue

            matches = find_matches(text)
            if not matches:
                continue

            labels = [match["label"] for match in matches]
            categories = sorted({match["category"] for match in matches})
            candidate_score = score_candidate(matches)
            noise_risk = compute_noise_risk(matches)

            article.pop("__line_number", None)

            article["matched_definition_patterns"] = labels
            article["matched_pattern_categories"] = categories
            article["candidate_score"] = candidate_score
            article["noise_risk"] = noise_risk
            article["text_preview"] = make_preview(text)

            out.write(json.dumps(article, ensure_ascii=False) + "\n")

            kept += 1
            pattern_counter.update(labels)
            category_counter.update(categories)
            noise_counter[noise_risk] += 1
            source_code_counter[article.get("source_code", "unknown")] += 1

    print(f"Input file: {INPUT_JSONL}")
    print(f"Output file: {OUTPUT_JSONL}")
    print(f"Input articles: {total}")
    print(f"Candidate articles: {kept}")
    print(f"Skipped empty text: {skipped_empty_text}")

    print("\nMatched pattern distribution:")
    for pattern, count in pattern_counter.most_common():
        print(f"- {pattern}: {count}")

    print("\nPattern category distribution:")
    for category, count in category_counter.most_common():
        print(f"- {category}: {count}")

    print("\nNoise risk distribution:")
    for risk, count in noise_counter.most_common():
        print(f"- {risk}: {count}")

    print("\nTop source codes among candidates:")
    for source_code, count in source_code_counter.most_common(20):
        print(f"- {source_code}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
