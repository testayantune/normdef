#!/usr/bin/env python3
"""
Strict draft extraction of candidate normative definitions from the NormDef-FR v0.2 annotation batch.

This script is intentionally conservative.

Input:
    data/annotation/annotation_batch_v0_2_articles.jsonl

Output:
    data/annotation/annotation_batch_v0_2_draft_definitions_strict.jsonl

Usage:
    python scripts/draft_extract_definitions_from_batch_strict.py

Important:
    This script produces DRAFT annotations, not gold annotations.

    It extracts only relatively reliable definition-like structures.
    No output should be considered gold without manual review.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_articles.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_draft_definitions_strict.jsonl"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Load JSONL rows one by one."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}\n"
            "Run scripts/sample_annotation_batch_v0_4.py first."
        )

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] Line {line_number}: invalid JSON: {exc}")
                continue

            if not isinstance(row, dict):
                print(f"[WARN] Line {line_number}: expected JSON object")
                continue

            row["__line_number"] = line_number
            yield row


def normalize_text(text: str) -> str:
    """Normalize whitespace and unusual Unicode line separators."""
    text = text.replace("\xa0", " ")
    text = text.replace("\u2028", "\n")
    text = text.replace("\u2029", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def clean_span(text: str | None) -> str | None:
    """Clean an extracted span without rewriting legal content."""
    if text is None:
        return None

    text = normalize_text(text)
    text = text.strip(" \t\n\r;.")
    return text.strip() or None


def truncate_at_boundary(text: str, max_chars: int = 900) -> str:
    """
    Cut a candidate definition at likely legal boundaries.

    This avoids extremely long draft spans.
    """
    text = normalize_text(text)

    boundaries = [
        r"\n\d+°\s",
        r"\n[a-z]\)\s",
        r"\n\n",
    ]

    for boundary in boundaries:
        parts = re.split(boundary, text, maxsplit=1)
        if parts:
            text = parts[0]

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."

    return clean_span(text) or ""


def infer_scope(text: str) -> tuple[str | None, str, str]:
    """
    Infer explicit and minimal scope.

    Returns:
        scope_text, scope_label, inferred_scope
    """
    scope_patterns = [
        (r"\b(?:pour l['’]application|au sens|aux fins) du présent article\b", "article"),
        (r"\b(?:pour l['’]application|au sens|aux fins) de la présente section\b", "section"),
        (r"\b(?:pour l['’]application|au sens|aux fins) du présent chapitre\b", "chapitre"),
        (r"\b(?:pour l['’]application|au sens|aux fins) du présent titre\b", "titre"),
        (r"\b(?:pour l['’]application|au sens|aux fins) du présent livre\b", "livre"),
        (r"\b(?:pour l['’]application|au sens|aux fins) du présent code\b", "code"),
    ]

    for pattern, label in scope_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            scope_text = match.group(0)
            return scope_text, label, label

    return None, "unspecified", "article"


def safe_id_part(value: Any) -> str:
    """Make an ID-safe fragment."""
    value = str(value or "UNK")
    value = (
        value.replace("É", "E")
        .replace("È", "E")
        .replace("Ê", "E")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("Î", "I")
        .replace("Ô", "O")
        .replace("Û", "U")
        .replace("Ç", "C")
    )
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return value or "UNK"


def make_definition_id(article: dict[str, Any], index: int) -> str:
    """Create a stable candidate definition ID."""
    source_part = safe_id_part(article.get("source_code", "UNK"))[:60]
    article_part = safe_id_part(article.get("article_number", "UNK"))[:30]
    article_id = str(article.get("article_id", "NOID")).replace("LEGIARTI", "ARTI")
    return f"DRAFT_{source_part}_{article_part}_{article_id}_{index:03d}"


def base_output_record(
    article: dict[str, Any],
    index: int,
    pattern: str,
    term_candidate: str | None,
    definition_candidate: str | None,
    raw_body: str,
    definition_type: str,
    extraction_confidence: str,
    extraction_comment: str | None = None,
) -> dict[str, Any]:
    """Build one strict draft definition record."""
    scope_text, scope_label, inferred_scope = infer_scope(raw_body)

    return {
        "candidate_definition_id": make_definition_id(article, index),
        "article_id": article.get("article_id"),
        "source_code": article.get("source_code"),
        "article_number": article.get("article_number"),
        "etat": article.get("etat"),
        "date_debut": article.get("date_debut"),
        "date_fin": article.get("date_fin"),
        "source_file": article.get("source_file"),

        "sampling_stratum": article.get("sampling_stratum"),
        "noise_risk": article.get("noise_risk"),
        "matched_definition_patterns": article.get("matched_definition_patterns"),
        "matched_pattern_categories": article.get("matched_pattern_categories"),
        "candidate_score": article.get("candidate_score"),

        "item_number": None,
        "defined_subject": None,
        "term_candidate": term_candidate,
        "definition_candidate": definition_candidate,
        "scope_text": scope_text,
        "scope_label": scope_label,
        "inferred_scope": inferred_scope,
        "pattern": pattern,
        "definition_type": definition_type,
        "raw_body": raw_body,

        "extraction_confidence": extraction_confidence,
        "extraction_comment": extraction_comment,

        # Manual annotation fields
        "manual_label": None,          # valid_definition / invalid / partial / unsure
        "gold_definition_id": None,
        "gold_term": None,
        "gold_definition": None,
        "gold_scope_text": None,
        "gold_scope_label": None,
        "gold_inferred_scope": None,
        "gold_definition_type": None,
        "correction_notes": None,
    }


def is_bad_colon_context(term: str, definition: str, raw_body: str) -> bool:
    """Reject colon matches that are clearly not term-definition structures."""
    term_l = term.lower()
    body_l = raw_body.lower()

    bad_term_fragments = [
        "sont soumises aux dispositions suivantes",
        "sont soumis aux dispositions suivantes",
        "est soumis aux dispositions suivantes",
        "sont applicables",
        "s'appliquent",
        "ne s'appliquent pas",
        "doivent comporter",
        "comprennent notamment",
        "comprend notamment",
        "sont fixées",
        "sont fixés",
        "sont déterminées",
        "sont déterminés",
    ]

    if any(fragment in term_l for fragment in bad_term_fragments):
        return True

    bad_body_fragments = [
        "sont soumises aux dispositions suivantes :",
        "sont soumis aux dispositions suivantes :",
        "doivent comporter :",
        "comprennent :",
        "comprend :",
        "sont fixées par :",
        "sont fixés par :",
    ]

    if any(fragment in body_l for fragment in bad_body_fragments):
        return True

    # Reject very sentence-like terms.
    if len(term.split()) > 12:
        return True

    # Reject if the "term" starts like a full legal sentence rather than a nominal term.
    bad_starts = (
        "les dispositions",
        "les conditions",
        "les modalités",
        "les règles",
        "les mesures",
        "le ministre",
        "la décision",
        "l'autorité",
    )
    if term_l.startswith(bad_starts):
        return True

    return False



def is_bad_term(term: str) -> bool:
    """Reject obvious non-term candidates before creating draft records."""
    term_l = term.lower().strip()

    if term_l in {
        "qui", "que", "dont", "où", "ou",
        "précité", "précitée", "précités", "précitées",
        "susvisé", "susvisée", "susvisés", "susvisées",
    }:
        return True

    bad_prefixes = (
        "au titre",
        "aux titres",
        "au chapitre",
        "aux chapitres",
        "au livre",
        "aux livres",
        "à la section",
        "aux sections",
        "aux articles",
        "les articles",
        "l'article",
        "du ",
        "de l'article",
        "territoires composition",
        "constituent des",
        "constituent les",
        "sont applicables",
        "sont soumis",
        "sont soumises",
    )

    bad_contains = (
        "communes de",
        "articles l.",
        "article l.",
        "dispositions abrogées",
    )

    if term_l.startswith(bad_prefixes):
        return True

    if any(fragment in term_l for fragment in bad_contains):
        return True

    if re.search(r"\barticles?\s+\d+\b", term_l):
        return True

    if re.search(
        r"\b\d{1,2}\s+"
        r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
        r"septembre|octobre|novembre|décembre|decembre)\s+\d{4}\b",
        term_l,
    ):
        return True

    if len(term.split()) > 10:
        return True

    return False

# ---------------------------------------------------------------------------
# Strict extractors
# ---------------------------------------------------------------------------

def extract_colon_definitions(article: dict[str, Any], text: str, start_index: int) -> list[dict[str, Any]]:
    """
    Extract strict glossary-like colon definitions.

    Examples:
        Consommateur : toute personne physique...
        Déchet : toute substance...
        1° Consommateur : toute personne physique...
    """
    records = []

    pattern = re.compile(
        r"(?P<item>\d+°\s*)?"
        r"(?P<term>[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ0-9'’\-\s]{2,80})"
        r"\s*:\s+"
        r"(?P<definition>"
        r"(?:un|une|des|du|de la|de l'|d'|tout|toute|tous|toutes|la|le|les|l')\b"
        r"[^;\n]{10,500}"
        r")",
        flags=re.IGNORECASE,
    )

    idx = start_index
    for match in pattern.finditer(text):
        item_number = clean_span(match.group("item")) if match.group("item") else None
        term = clean_span(match.group("term"))
        definition = clean_span(match.group("definition"))
        raw_body = clean_span(match.group(0))

        if not term or is_bad_term(term) or not definition or not raw_body:
            continue

        if is_bad_colon_context(term, definition, raw_body):
            continue

        record = base_output_record(
            article=article,
            index=idx,
            pattern="terme_colon_definition",
            term_candidate=term,
            definition_candidate=definition,
            raw_body=raw_body,
            definition_type="explicit",
            extraction_confidence="high",
        )
        record["item_number"] = item_number
        records.append(record)
        idx += 1

    return records


def extract_on_entend_par(article: dict[str, Any], text: str, start_index: int) -> list[dict[str, Any]]:
    """
    Extract definitions introduced by 'on entend par'.

    Handles:
        On entend par X ...
        Pour l'application du présent code, on entend par X ...
    """
    records = []

    pattern = re.compile(
        r"(?P<prefix>(?:pour l['’]application|au sens|aux fins)[^,.:\n]{0,140}[,:\s]+)?"
        r"on entend par\s+"
        r"[«\"]?"
        r"(?P<term>[^,»\":\n]{2,100})"
        r"[»\"]?"
        r"\s*(?:,|:)?\s+"
        r"(?P<definition>"
        r"(?:un|une|des|du|de la|de l'|d'|tout|toute|tous|toutes|la|le|les|l'|toute personne|tout médicament|toute substance)\b"
        r".{10,900}"
        r")",
        flags=re.IGNORECASE | re.DOTALL,
    )

    idx = start_index
    for match in pattern.finditer(text):
        term = clean_span(match.group("term"))
        definition = truncate_at_boundary(match.group("definition"), max_chars=800)
        raw_body = clean_span(match.group(0))

        if not term or is_bad_term(term) or not definition or not raw_body:
            continue

        # Avoid absurd terms.
        if len(term.split()) > 12:
            continue

        if len(raw_body) > 1100:
            raw_body = raw_body[:1100].rstrip() + "..."

        record = base_output_record(
            article=article,
            index=idx,
            pattern="on entend par",
            term_candidate=term,
            definition_candidate=definition,
            raw_body=raw_body,
            definition_type="explicit",
            extraction_confidence="high",
        )
        records.append(record)
        idx += 1

    return records


def extract_s_entend_de(article: dict[str, Any], text: str, start_index: int) -> list[dict[str, Any]]:
    """
    Extract definitions using 's'entend de / s'entendent de'.

    Handles:
        La probité, qui s'entend de l'exigence générale d'honnêteté, ...
        Le terme X s'entend de ...
        Les mots X s'entendent de ...
    """
    records = []

    patterns = [
        # "La probité, qui s'entend de l'exigence générale d'honnêteté, ..."
        re.compile(
            r"\b(?:le|la|les|l['’])\s+"
            r"(?P<term>[A-Za-zÀ-ÖØ-öø-ÿ'’\-\s]{2,80}?)"
            r"\s*,\s*qui\s+s['’]entend(?:ent)?\s+de\s+"
            r"(?P<definition>[^.;,\n]{5,300})",
            flags=re.IGNORECASE,
        ),
        # "Le terme X s'entend de ..."
        re.compile(
            r"\b(?:le terme|les termes|le mot|les mots|l['’]expression)\s+"
            r"[«\"]?"
            r"(?P<term>[^»\".,:\n]{2,100})"
            r"[»\"]?"
            r"\s+s['’]entend(?:ent)?\s+(?:de|comme|par)\s+"
            r"(?P<definition>[^.;\n]{5,400})",
            flags=re.IGNORECASE,
        ),
        # "X s'entend de ..." with short nominal subject only.
        re.compile(
            r"(?<!\.)\b"
            r"(?P<term>[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ'’\-\s]{2,80})"
            r"\s+s['’]entend(?:ent)?\s+(?:de|comme|par)\s+"
            r"(?P<definition>[^.;\n]{5,400})",
            flags=re.IGNORECASE,
        ),
    ]

    idx = start_index
    for pattern in patterns:
        for match in pattern.finditer(text):
            term = clean_span(match.group("term"))
            definition = clean_span(match.group("definition"))
            raw_body = clean_span(match.group(0))

            if not term or is_bad_term(term) or not definition or not raw_body:
                continue

            # Avoid overly long sentence fragments as terms.
            if len(term.split()) > 8:
                continue

            record = base_output_record(
                article=article,
                index=idx,
                pattern="s'entend de",
                term_candidate=term,
                definition_candidate=definition,
                raw_body=raw_body,
                definition_type="explicit",
                extraction_confidence="high",
            )
            records.append(record)
            idx += 1

    return records


def extract_defini_comme(article: dict[str, Any], text: str, start_index: int) -> list[dict[str, Any]]:
    """
    Extract only strict 'défini comme' definitions.

    We intentionally do NOT extract broad 'est défini par' / 'sont définis par'
    because those often express external legal delegation, not a definition.
    """
    records = []

    pattern = re.compile(
        r"(?P<term>[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ0-9'’\-\s]{2,80})"
        r"\s*,?\s+défini(?:e|s|es)?\s+comme\s+"
        r"(?P<definition>[^.;\n]{10,500})",
        flags=re.IGNORECASE,
    )

    idx = start_index
    for match in pattern.finditer(text):
        term = clean_span(match.group("term"))
        definition = clean_span(match.group("definition"))
        raw_body = clean_span(match.group(0))

        if not term or is_bad_term(term) or not definition or not raw_body:
            continue

        if len(term.split()) > 10:
            continue

        record = base_output_record(
            article=article,
            index=idx,
            pattern="défini comme",
            term_candidate=term,
            definition_candidate=definition,
            raw_body=raw_body,
            definition_type="explicit",
            extraction_confidence="medium",
            extraction_comment="Strict extraction for 'défini comme'; manual validation required.",
        )
        records.append(record)
        idx += 1

    return records


def extract_strict_qualification(article: dict[str, Any], text: str, start_index: int) -> list[dict[str, Any]]:
    """
    Extract only relatively clean qualification definitions.

    We do NOT extract 'est réputé' / 'sont réputés' here because they often express
    legal presumptions rather than term-definition structures.
    """
    records = []

    patterns = [
        (
            "est qualifié de",
            re.compile(
                r"(?P<subject>[^.;\n]{2,120}?)\s+est qualifié(?:e)? de\s+"
                r"(?P<term>[^.;,\n]{2,80})\s+"
                r"(?P<trigger>lorsqu[’']?il|lorsque|si)\s+"
                r"(?P<definition>[^.;\n]{5,400})",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "sont qualifiés de",
            re.compile(
                r"(?P<subject>[^.;\n]{2,120}?)\s+sont qualifié(?:e)?s de\s+"
                r"(?P<term>[^.;,\n]{2,80})\s+"
                r"(?P<trigger>lorsqu[’']?ils|lorsque|si)\s+"
                r"(?P<definition>[^.;\n]{5,400})",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "est considéré comme",
            re.compile(
                r"(?P<subject>[^.;\n]{2,120}?)\s+est considéré(?:e)? comme\s+"
                r"(?P<term>[^.;,\n]{2,80})\s+"
                r"(?P<trigger>lorsqu[’']?il|lorsque|si)\s+"
                r"(?P<definition>[^.;\n]{5,400})",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "sont considérés comme",
            re.compile(
                r"(?P<subject>[^.;\n]{2,120}?)\s+sont considéré(?:e)?s comme\s+"
                r"(?P<term>[^.;,\n]{2,80})\s+"
                r"(?P<trigger>lorsqu[’']?ils|lorsque|si)\s+"
                r"(?P<definition>[^.;\n]{5,400})",
                flags=re.IGNORECASE,
            ),
        ),
    ]

    idx = start_index
    for label, pattern in patterns:
        for match in pattern.finditer(text):
            subject = clean_span(match.group("subject"))
            term = clean_span(match.group("term"))
            definition = clean_span(match.group("definition"))
            raw_body = clean_span(match.group(0))

            if not subject or not term or is_bad_term(term) or not definition or not raw_body:
                continue

            if len(subject.split()) > 15 or len(term.split()) > 10:
                continue

            record = base_output_record(
                article=article,
                index=idx,
                pattern=label,
                term_candidate=term,
                definition_candidate=definition,
                raw_body=raw_body,
                definition_type="explicit_qualification",
                extraction_confidence="medium",
                extraction_comment="Qualification pattern extracted only when a condition trigger is present.",
            )
            record["defined_subject"] = subject
            records.append(record)
            idx += 1

    return records


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate draft records for the same article/span."""
    seen: set[tuple[Any, Any, Any, Any]] = set()
    deduped: list[dict[str, Any]] = []

    for record in records:
        key = (
            record.get("article_id"),
            record.get("pattern"),
            record.get("term_candidate"),
            record.get("definition_candidate"),
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(record)

    return deduped


def extract_from_article(article: dict[str, Any]) -> list[dict[str, Any]]:
    """Run all strict draft extraction heuristics on one article."""
    text = article.get("text") or ""
    if not isinstance(text, str) or not text.strip():
        return []

    text = normalize_text(text)

    records: list[dict[str, Any]] = []
    records.extend(extract_colon_definitions(article, text, start_index=1000))
    records.extend(extract_on_entend_par(article, text, start_index=2000))
    records.extend(extract_s_entend_de(article, text, start_index=3000))
    records.extend(extract_defini_comme(article, text, start_index=4000))
    records.extend(extract_strict_qualification(article, text, start_index=5000))

    return dedupe_records(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    articles_read = 0
    articles_with_drafts = 0
    draft_count = 0

    pattern_counter: Counter[str] = Counter()
    confidence_counter: Counter[str] = Counter()
    noise_counter: Counter[str] = Counter()
    stratum_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for article in load_jsonl(INPUT_FILE):
            articles_read += 1

            drafts = extract_from_article(article)

            if drafts:
                articles_with_drafts += 1

            for draft in drafts:
                out.write(json.dumps(draft, ensure_ascii=False) + "\n")
                draft_count += 1

                pattern_counter[draft.get("pattern", "unknown")] += 1
                confidence_counter[draft.get("extraction_confidence", "unknown")] += 1
                noise_counter[str(draft.get("noise_risk", "unknown"))] += 1
                stratum_counter[str(draft.get("sampling_stratum", "unknown"))] += 1
                source_counter[str(draft.get("source_code", "unknown"))] += 1

    print(f"Input file: {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Articles read: {articles_read}")
    print(f"Articles with strict draft definitions: {articles_with_drafts}")
    print(f"Strict draft definitions extracted: {draft_count}")

    print("\nStrict drafts by pattern:")
    for pattern, count in pattern_counter.most_common():
        print(f"- {pattern}: {count}")

    print("\nStrict drafts by extraction confidence:")
    for confidence, count in confidence_counter.most_common():
        print(f"- {confidence}: {count}")

    print("\nStrict drafts by noise risk:")
    for risk, count in noise_counter.most_common():
        print(f"- {risk}: {count}")

    print("\nStrict drafts by sampling stratum:")
    for stratum, count in stratum_counter.most_common():
        print(f"- {stratum}: {count}")

    print("\nTop source codes:")
    for source, count in source_counter.most_common(20):
        print(f"- {source}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
