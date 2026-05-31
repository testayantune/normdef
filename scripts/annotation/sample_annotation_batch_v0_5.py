#!/usr/bin/env python3
"""
Create NormDef-FR v0.5 annotation batch with robust exclusion of existing gold/manual articles
AND existing gold terms by source_code + term.

Goal:
    Build a large clean v0.5 annotation batch to extend NormDef-FR toward ~600 gold records,
    while preventing re-sampling of:
        1. articles already present in the current gold/manual datasets;
        2. articles containing a term already present in the same source_code.

Input:
    data/candidates/candidate_definition_articles_low_clean.jsonl

Main exclusion source:
    data/normdef_fr_v0_4_gold.jsonl

Additional exclusion sources:
    data/normv1.0.json
    data/annotation/normdef_fr_v0_2_gold_from_review.jsonl
    data/annotation/normdef_fr_v0_3_gold_from_review.jsonl
    data/annotation/annotation_batch_v0_2_articles.jsonl
    data/annotation/annotation_batch_v0_3_articles.jsonl
    data/annotation/annotation_batch_v0_2_reviewed.jsonl
    data/annotation/annotation_batch_v0_3_reviewed.jsonl

Output:
    data/annotation/annotation_batch_v0_5_articles.jsonl
    data/annotation/annotation_batch_v0_5_sampling_summary.json
    data/annotation/annotation_batch_v0_5_excluded_existing_articles.jsonl
    data/annotation/annotation_batch_v0_5_excluded_existing_terms.jsonl

Usage:
    python scripts/sample_annotation_batch_v0_5.py

Important:
    This is v0.5.
    It includes v0.4 files in EXCLUSION_FILES because v0.5 must not reuse v0.4 material.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BATCH_VERSION = "v0.5"
BATCH_VERSION_FILE = "v0_5"

INPUT_FILE = PROJECT_ROOT / "data" / "candidates" / "candidate_definition_articles_low_clean.jsonl"

EXCLUSION_FILES = [
    PROJECT_ROOT / "data" / "normdef_fr_v0_4_gold.jsonl",
    PROJECT_ROOT / "data" / "normdef_fr_v0_3_gold.jsonl",
    PROJECT_ROOT / "data" / "normv1.0.json",
    PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_2_gold_from_review.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_3_gold_from_review.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "normdef_fr_v0_4_gold_from_review.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_2_articles.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_3_articles.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_articles.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_2_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_3_reviewed.jsonl",
    PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_4_reviewed.jsonl",
]

OUTPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_articles.jsonl"
OUTPUT_SUMMARY = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_sampling_summary.json"
OUTPUT_EXCLUDED_ARTICLES = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_excluded_existing_articles.jsonl"
OUTPUT_EXCLUDED_TERMS = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_excluded_existing_terms.jsonl"

RANDOM_SEED = 55
N_SAMPLE = 2000
MAX_PER_SOURCE_CODE = 60

PRIORITY_PATTERNS = {
    "on entend par",
    "s'entend de",
    "terme_colon_definition",
    "guillemets_définition",
    "défini comme",
    "sont définis",
    "est défini",
    "au sens du présent",
    "au sens du présent étendu",
    "au sens de la présente",
    "pour l'application du présent",
    "pour l'application de la présente",
    "sont considérés comme",
    "est considéré comme",
}


def load_records(path: Path, required: bool = False) -> list[dict[str, Any]]:
    """
    Load records from JSONL or JSON.
    Supports JSONL, JSON array, or JSON object containing data/records/definitions/items.
    """
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        print(f"[WARN] Optional file not found, skipped: {path}")
        return []

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        data = json.loads(text)

        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            for key in ("data", "records", "definitions", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
            return [data]

    except json.JSONDecodeError:
        pass

    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"[WARN] {path.name} line {line_number}: invalid JSON: {exc}")
            continue

        if isinstance(row, dict):
            rows.append(row)

    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_key(value: Any) -> str:
    """Normalize source/article values."""
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")

    text = text.replace("code rural (nouveau)", "code rural et de la pêche maritime")
    text = text.replace("code rural et de la peche maritime", "code rural et de la pêche maritime")

    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,")


def normalize_article_number(value: Any) -> str:
    text = normalize_key(value)

    if text in {"article liminaire", "art liminaire", "art. liminaire"}:
        return "liminaire"

    return text


def normalize_term(value: Any) -> str:
    """Normalize a legal term for source_code + term exclusion."""
    if value is None:
        return ""

    text = str(value).lower().strip()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")
    text = strip_accents(text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*'\s*", "'", text)
    return text.strip(" .;:,")


def normalized_text_for_search(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).lower()
    text = text.replace("’", "'")
    text = text.replace("\xa0", " ")
    text = strip_accents(text)
    text = re.sub(r"\s+", " ", text)
    return f" {text.strip()} "


def term_occurs_in_text(term: str, text: str) -> bool:
    term = normalize_term(term)
    if not term or len(term) < 3:
        return False

    text_norm = normalized_text_for_search(text)
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text_norm) is not None


def article_keys(row: dict[str, Any]) -> set[str]:
    """
    Build multiple article-level keys.
    This avoids relying only on article_id.
    """
    keys: set[str] = set()

    article_id = normalize_key(row.get("article_id"))
    source_file = normalize_key(row.get("source_file"))
    source_code = normalize_key(row.get("source_code"))
    article_number = normalize_article_number(row.get("article_number"))
    date_debut = normalize_key(row.get("date_debut"))
    date_fin = normalize_key(row.get("date_fin"))

    if article_id:
        keys.add(f"article_id::{article_id}")

    if source_file:
        keys.add(f"source_file::{source_file}")

    if source_code and article_number:
        keys.add(f"source_article::{source_code}::{article_number}")

    if source_code and article_number and date_debut and date_fin:
        keys.add(f"source_article_dates::{source_code}::{article_number}::{date_debut}::{date_fin}")

    return keys


def build_article_exclusion_index(paths: list[Path]) -> tuple[set[str], dict[str, list[str]], Counter[str]]:
    exclusion_keys: set[str] = set()
    key_to_sources: dict[str, list[str]] = defaultdict(list)
    stats: Counter[str] = Counter()

    for path in paths:
        rows = load_records(path, required=False)
        stats[f"{path.name}:rows_read"] = len(rows)

        for row in rows:
            keys = article_keys(row)

            if not keys:
                stats[f"{path.name}:rows_without_article_keys"] += 1
                continue

            for key in keys:
                exclusion_keys.add(key)
                key_to_sources[key].append(str(path))

            stats[f"{path.name}:rows_with_article_keys"] += 1

    return exclusion_keys, key_to_sources, stats


def possible_term_fields(row: dict[str, Any]) -> list[Any]:
    """
    Gold files usually use term.
    Reviewed draft files may use gold_term or term_candidate.
    """
    return [
        row.get("term"),
        row.get("gold_term"),
        row.get("term_candidate"),
    ]


def build_term_exclusion_index(paths: list[Path]) -> tuple[dict[str, set[str]], dict[tuple[str, str], list[str]], Counter[str]]:
    """
    Build source_code -> set(normalized terms).
    """
    terms_by_source: dict[str, set[str]] = defaultdict(set)
    term_key_to_sources: dict[tuple[str, str], list[str]] = defaultdict(list)
    stats: Counter[str] = Counter()

    for path in paths:
        rows = load_records(path, required=False)
        stats[f"{path.name}:rows_read_for_terms"] = len(rows)

        for row in rows:
            source_code = normalize_key(row.get("source_code"))
            if not source_code:
                stats[f"{path.name}:rows_without_source_code_for_terms"] += 1
                continue

            found_any_term = False

            for term_value in possible_term_fields(row):
                term = normalize_term(term_value)
                if not term:
                    continue

                found_any_term = True
                terms_by_source[source_code].add(term)
                term_key_to_sources[(source_code, term)].append(str(path))

            if found_any_term:
                stats[f"{path.name}:rows_with_terms"] += 1
            else:
                stats[f"{path.name}:rows_without_terms"] += 1

    return terms_by_source, term_key_to_sources, stats


def find_existing_terms_in_candidate(
    row: dict[str, Any],
    terms_by_source: dict[str, set[str]],
    term_key_to_sources: dict[tuple[str, str], list[str]],
) -> list[dict[str, Any]]:
    """
    Exclude a candidate article when it contains a gold term already present
    in the same source_code.
    """
    source_code = normalize_key(row.get("source_code"))
    if not source_code:
        return []

    terms = terms_by_source.get(source_code, set())
    if not terms:
        return []

    text = row.get("text") or row.get("raw_body") or ""
    if not isinstance(text, str) or not text.strip():
        return []

    matches: list[dict[str, Any]] = []

    for term in sorted(terms, key=len, reverse=True):
        if term_occurs_in_text(term, text):
            matches.append(
                {
                    "source_code": source_code,
                    "term": term,
                    "sources": sorted(set(term_key_to_sources.get((source_code, term), []))),
                }
            )

    return matches


def pattern_priority_score(row: dict[str, Any]) -> int:
    patterns = row.get("matched_definition_patterns", [])
    if not isinstance(patterns, list):
        patterns = []

    score = 0

    for pattern in patterns:
        if pattern in PRIORITY_PATTERNS:
            score += 3
        else:
            score += 1

    try:
        score += int(row.get("candidate_score", 0))
    except (TypeError, ValueError):
        pass

    if row.get("noise_risk") == "low":
        score += 2

    if row.get("sampling_stratum") == "low_clean":
        score += 1

    return score


def has_required_text(row: dict[str, Any]) -> bool:
    text = row.get("text") or row.get("raw_body") or ""
    return isinstance(text, str) and bool(text.strip())


def balanced_priority_sample(
    rows: list[dict[str, Any]],
    n: int,
    max_per_code: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        source_code = str(row.get("source_code", "unknown"))
        grouped[source_code].append(row)

    for group in grouped.values():
        rng.shuffle(group)
        group.sort(key=pattern_priority_score, reverse=True)

    codes = list(grouped.keys())
    rng.shuffle(codes)

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    selected_by_code: Counter[str] = Counter()

    while len(selected) < n:
        made_progress = False

        for code in codes:
            if len(selected) >= n:
                break

            if selected_by_code[code] >= max_per_code:
                continue

            group = grouped[code]

            while group:
                candidate = group.pop(0)
                keys = article_keys(candidate)

                if keys & selected_keys:
                    continue

                selected.append(candidate)
                selected_keys.update(keys)
                selected_by_code[code] += 1
                made_progress = True
                break

        if not made_progress:
            break

    return selected


def add_annotation_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=1):
        row = dict(row)

        row["annotation_batch"] = BATCH_VERSION
        row["sampling_stratum"] = "low_clean_v0_5"
        row["manual_review_status"] = "pending"
        row["has_definition"] = None
        row["annotation_notes"] = None
        row["v0_5_sample_index"] = idx

        enriched.append(row)

    return enriched


def main() -> int:
    rows = load_records(INPUT_FILE, required=True)

    article_exclusion_keys, key_to_sources, article_stats = build_article_exclusion_index(EXCLUSION_FILES)
    terms_by_source, term_key_to_sources, term_stats = build_term_exclusion_index(EXCLUSION_FILES)

    filtered_rows: list[dict[str, Any]] = []
    excluded_article_rows: list[dict[str, Any]] = []
    excluded_term_rows: list[dict[str, Any]] = []

    excluded_article_count = 0
    excluded_term_count = 0
    empty_text_count = 0
    no_article_key_count = 0

    for row in rows:
        keys = article_keys(row)

        if not keys:
            no_article_key_count += 1

        article_matches = keys & article_exclusion_keys

        if article_matches:
            excluded_article_count += 1
            excluded = dict(row)
            excluded["_exclusion_reason"] = "existing_article"
            excluded["_exclusion_matched_keys"] = sorted(article_matches)
            excluded["_exclusion_sources"] = sorted(
                {
                    source
                    for key in article_matches
                    for source in key_to_sources.get(key, [])
                }
            )
            excluded_article_rows.append(excluded)
            continue

        term_matches = find_existing_terms_in_candidate(
            row=row,
            terms_by_source=terms_by_source,
            term_key_to_sources=term_key_to_sources,
        )

        if term_matches:
            excluded_term_count += 1
            excluded = dict(row)
            excluded["_exclusion_reason"] = "existing_source_code_term"
            excluded["_matched_existing_terms"] = term_matches
            excluded_term_rows.append(excluded)
            continue

        if not has_required_text(row):
            empty_text_count += 1
            continue

        filtered_rows.append(row)

    if not filtered_rows:
        raise RuntimeError("No eligible rows left after robust article and term exclusions.")

    selected = balanced_priority_sample(
        rows=filtered_rows,
        n=N_SAMPLE,
        max_per_code=MAX_PER_SOURCE_CODE,
        seed=RANDOM_SEED,
    )

    selected = add_annotation_fields(selected)

    write_jsonl(OUTPUT_FILE, selected)
    write_jsonl(OUTPUT_EXCLUDED_ARTICLES, excluded_article_rows)
    write_jsonl(OUTPUT_EXCLUDED_TERMS, excluded_term_rows)

    source_counter = Counter(str(row.get("source_code", "unknown")) for row in selected)
    pattern_counter: Counter[str] = Counter()
    score_counter: Counter[int] = Counter()

    for row in selected:
        patterns = row.get("matched_definition_patterns", [])
        if isinstance(patterns, list):
            pattern_counter.update(str(pattern) for pattern in patterns)

        try:
            score_counter[int(row.get("candidate_score", 0))] += 1
        except (TypeError, ValueError):
            score_counter[0] += 1

    summary = {
        "batch_version": BATCH_VERSION,
        "input_file": str(INPUT_FILE),
        "output_file": str(OUTPUT_FILE),
        "excluded_existing_articles_file": str(OUTPUT_EXCLUDED_ARTICLES),
        "excluded_existing_terms_file": str(OUTPUT_EXCLUDED_TERMS),
        "random_seed": RANDOM_SEED,
        "requested_sample_size": N_SAMPLE,
        "actual_sample_size": len(selected),
        "max_per_source_code": MAX_PER_SOURCE_CODE,
        "input_rows": len(rows),
        "exclusion_article_keys_total": len(article_exclusion_keys),
        "gold_term_source_codes_total": len(terms_by_source),
        "gold_terms_total": sum(len(terms) for terms in terms_by_source.values()),
        "excluded_existing_articles": excluded_article_count,
        "excluded_existing_source_code_terms": excluded_term_count,
        "skipped_empty_text": empty_text_count,
        "rows_without_article_keys": no_article_key_count,
        "eligible_rows_after_exclusion": len(filtered_rows),
        "source_code_distribution": dict(source_counter),
        "matched_pattern_distribution": dict(pattern_counter),
        "candidate_score_distribution": dict(sorted(score_counter.items(), reverse=True)),
        "exclusion_files": [str(path) for path in EXCLUSION_FILES],
        "article_exclusion_file_stats": dict(article_stats),
        "term_exclusion_file_stats": dict(term_stats),
    }

    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Input file: {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Summary file: {OUTPUT_SUMMARY}")
    print(f"Excluded existing articles file: {OUTPUT_EXCLUDED_ARTICLES}")
    print(f"Excluded existing terms file: {OUTPUT_EXCLUDED_TERMS}")

    print(f"\nInput rows: {len(rows)}")
    print(f"Exclusion article keys total: {len(article_exclusion_keys)}")
    print(f"Gold term source codes total: {len(terms_by_source)}")
    print(f"Gold terms total: {sum(len(terms) for terms in terms_by_source.values())}")
    print(f"Excluded existing articles: {excluded_article_count}")
    print(f"Excluded existing source_code+term articles: {excluded_term_count}")
    print(f"Skipped empty text: {empty_text_count}")
    print(f"Rows without article keys: {no_article_key_count}")
    print(f"Eligible rows after exclusion: {len(filtered_rows)}")
    print(f"Sampled articles: {len(selected)}")
    print(f"Max per source code: {MAX_PER_SOURCE_CODE}")

    print("\nTop source codes in v0.5 batch:")
    for source_code, count in source_counter.most_common(30):
        print(f"- {source_code}: {count}")

    print("\nTop matched patterns in v0.5 batch:")
    for pattern, count in pattern_counter.most_common(30):
        print(f"- {pattern}: {count}")

    print("\nCandidate score distribution:")
    for score, count in sorted(score_counter.items(), reverse=True):
        print(f"- {score}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
