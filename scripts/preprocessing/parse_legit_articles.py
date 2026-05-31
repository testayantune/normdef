#!/usr/bin/env python3
"""
Parse LEGI code articles from a TAR archive without extracting all XML files to disk.

NormDef-FR version.

Goal:
    Build a clean article-level corpus from the LEGI global TAR archive.

Input:
    data/raw/Freemium_legi_global_20250713-140000.tar

Output:
    data/processed/articles_clean.jsonl

Usage:
    python scripts/parse_legi_articles.py

Output JSONL format:
    {
      "article_id": "...",
      "source_code": "...",
      "article_number": "...",
      "etat": "...",
      "date_debut": "...",
      "date_fin": "...",
      "text": "...",
      "source_file": "..."
    }

Important:
    - This script reads the .tar archive directly.
    - It does NOT extract all XML files to disk.
    - It excludes TNC material, including TNC_en_vigueur and TNC_non_vigueur.
    - It keeps only XML article files under code_et_TNC_en_vigueur.
"""

from __future__ import annotations

import json
import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ARCHIVE_PATH = RAW_DIR / "Freemium_legi_global_20250713-140000.tar"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "articles_clean.jsonl"

# Keep False for a general clean article corpus.
# Set True only if you want to parse only files containing obvious definitional markers.
PRE_FILTER_DEFINITIONAL_FILES = False

DEFINITION_PATTERNS = [
    "on entend par",
    "au sens du présent",
    "au sens de la présente",
    "pour l'application du présent",
    "pour l’application du présent",
    "défini comme",
    "définie comme",
    "définis comme",
    "définies comme",
    "sont qualifiés de",
    "est qualifié de",
    "sont considérés comme",
    "est considéré comme",
]


def local_name(tag: str) -> str:
    """Return XML local tag name without namespace."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def normalize_space(text: str) -> str:
    """Normalize whitespace and remove unusual Unicode line terminators."""
    text = text.replace("\xa0", " ")
    text = text.replace("\u2028", "\n")  # Unicode line separator
    text = text.replace("\u2029", "\n")  # Unicode paragraph separator
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def text_content(element: ET.Element) -> str:
    """Extract all textual content from an XML element."""
    parts: list[str] = []

    for text in element.itertext():
        if text and text.strip():
            parts.append(text.strip())

    return normalize_space(" ".join(parts))


def find_first_child_text(element: ET.Element, candidate_names: set[str]) -> Optional[str]:
    """Find the first non-empty text from descendants with selected local tag names."""
    for child in element.iter():
        if local_name(child.tag) in candidate_names:
            value = text_content(child)
            if value:
                return value

    return None


def find_direct_or_nested_attr(element: ET.Element, attr_names: set[str]) -> Optional[str]:
    """Find the first matching attribute on the element or descendants."""
    for node in element.iter():
        for attr_name, attr_value in node.attrib.items():
            if local_name(attr_name) in attr_names or attr_name in attr_names:
                if attr_value and attr_value.strip():
                    return attr_value.strip()

    return None


def is_relevant_code_article(member_name: str) -> bool:
    """
    Keep only article XML files from actual legal codes in force.

    Why this filter exists:
        A file can be under `code_et_TNC_en_vigueur` while still being
        non-codified TNC material, for example:
        `.../TNC_en_vigueur/JORF/TEXT/.../article/...`

        Such files are not code articles and must be excluded for NormDef-FR.

    Kept:
        - XML files;
        - article-like files;
        - under code_et_TNC_en_vigueur;
        - not under any TNC folder.

    Excluded:
        - code_et_TNC_non_vigueur;
        - TNC_en_vigueur;
        - TNC_non_vigueur;
        - non-article XML files.
    """
    name = member_name.replace("\\", "/").lower()

    if not name.endswith(".xml"):
        return False

    if "/article/" not in name and "legiarti" not in name:
        return False

    if "code_et_tnc_non_vigueur" in name:
        return False

    if "/tnc_en_vigueur/" in name:
        return False

    if "/tnc_non_vigueur/" in name:
        return False

    if "code_et_tnc_en_vigueur" not in name:
        return False

    return True


def contains_definition_marker(xml_bytes: bytes) -> bool:
    """
    Optional fast pre-filter.

    Disabled by default because some legal definitions are compact colon
    definitions and may not contain a strong marker.
    """
    text = xml_bytes[:200000].decode("utf-8", errors="ignore").lower()
    return any(pattern in text for pattern in DEFINITION_PATTERNS)


def infer_source_code_from_path(member_name: str) -> str:
    """Infer source code name from archive member path as fallback."""
    lower = member_name.lower()

    known = {
        "code de la consommation": "Code de la consommation",
        "code_de_la_consommation": "Code de la consommation",
        "code-de-la-consommation": "Code de la consommation",
        "code de l'environnement": "Code de l'environnement",
        "code_de_l_environnement": "Code de l'environnement",
        "code-de-l-environnement": "Code de l'environnement",
        "code du travail": "Code du travail",
        "code_du_travail": "Code du travail",
        "code-du-travail": "Code du travail",
        "code de la santé publique": "Code de la santé publique",
        "code_de_la_sante_publique": "Code de la santé publique",
        "code-de-la-sante-publique": "Code de la santé publique",
        "code des postes": "Code des postes et des communications électroniques",
        "code_des_postes": "Code des postes et des communications électroniques",
        "code-des-postes": "Code des postes et des communications électroniques",
    }

    for key, value in known.items():
        if key in lower:
            return value

    return "unknown"


def extract_source_code(root: ET.Element, member_name: str) -> str:
    """
    Try to extract the legal code title from XML metadata.

    LEGI XML structures vary, so we check several possible metadata tags.
    If no usable code title is found, we fall back to path inference.
    """
    candidate_tags = {
        "TITRE_TXT",
        "TITRE",
        "TITREFULL",
        "NOM_CODE",
        "LIBELLE",
        "TITLE",
    }

    possible_values: list[str] = []

    for node in root.iter():
        if local_name(node.tag) in candidate_tags:
            value = text_content(node)
            if value and "code" in value.lower():
                possible_values.append(value)

    if possible_values:
        possible_values = sorted(set(possible_values), key=len)
        return possible_values[0]

    return infer_source_code_from_path(member_name)


def extract_article_number(article: ET.Element) -> Optional[str]:
    """Extract article number from common LEGI fields."""
    value = find_first_child_text(article, {"NUM", "NUM_ARTICLE", "ARTICLE_NUM", "NUMERO"})
    if value:
        return value

    return find_direct_or_nested_attr(article, {"num", "numero", "NUM", "NUMERO"})


def extract_article_id(article: ET.Element) -> Optional[str]:
    """Extract article identifier from common LEGI fields."""
    value = find_first_child_text(article, {"ID", "CID", "ID_ARTICLE"})
    if value:
        return value

    return find_direct_or_nested_attr(article, {"id", "cid", "ID", "CID"})


def extract_article_state(article: ET.Element) -> Optional[str]:
    """Extract article legal state when available."""
    return find_first_child_text(article, {"ETAT", "ETAT_JURIDIQUE"})


def extract_date(article: ET.Element, names: set[str]) -> Optional[str]:
    """Extract date from common XML tags or attributes."""
    value = find_first_child_text(article, names)
    if value:
        return value

    return find_direct_or_nested_attr(article, names)


def extract_article_text(article: ET.Element) -> str:
    """
    Extract article textual content.

    Priority:
        1. BLOC_TEXTUEL or CONTENU blocks.
        2. Full ARTICLE text as fallback.
    """
    priority_tags = {"BLOC_TEXTUEL", "CONTENU"}
    collected: list[str] = []

    for node in article.iter():
        if local_name(node.tag) in priority_tags:
            value = text_content(node)
            if value:
                collected.append(value)

    if collected:
        seen: set[str] = set()
        unique: list[str] = []

        for value in collected:
            if value not in seen:
                seen.add(value)
                unique.append(value)

        return normalize_space("\n\n".join(unique))

    return text_content(article)


def iter_articles(root: ET.Element):
    """Yield all ARTICLE elements from a parsed XML tree."""
    for node in root.iter():
        if local_name(node.tag) == "ARTICLE":
            yield node


def parse_xml_bytes(xml_bytes: bytes, member_name: str) -> list[dict[str, object]]:
    """Parse one XML file loaded from the TAR archive."""
    rows: list[dict[str, object]] = []

    if PRE_FILTER_DEFINITIONAL_FILES and not contains_definition_marker(xml_bytes):
        return rows

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return rows

    source_code = extract_source_code(root, member_name)

    for article in iter_articles(root):
        text = extract_article_text(article)
        if not text:
            continue

        article_number = extract_article_number(article)
        article_id = extract_article_id(article)

        if not article_number and not article_id:
            continue

        rows.append(
            {
                "article_id": article_id,
                "source_code": source_code,
                "article_number": article_number,
                "etat": extract_article_state(article),
                "date_debut": extract_date(article, {"DEBUT", "DATE_DEBUT", "DATEDEBUT"}),
                "date_fin": extract_date(article, {"FIN", "DATE_FIN", "DATEFIN"}),
                "text": text,
                "source_file": member_name,
            }
        )

    return rows


def main() -> int:
    if not ARCHIVE_PATH.exists():
        raise FileNotFoundError(
            f"Archive not found: {ARCHIVE_PATH}\n"
            f"Put the TAR archive in: {RAW_DIR}"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    total_members = 0
    skipped_members = 0
    relevant_xml_files = 0
    xml_files_with_articles = 0
    total_articles = 0

    with tarfile.open(ARCHIVE_PATH, mode="r:") as tar, OUTPUT_FILE.open(
        "w", encoding="utf-8"
    ) as out:
        for member in tar:
            total_members += 1

            if not member.isfile():
                skipped_members += 1
                continue

            if not is_relevant_code_article(member.name):
                skipped_members += 1
                continue

            relevant_xml_files += 1

            extracted = tar.extractfile(member)
            if extracted is None:
                continue

            xml_bytes = extracted.read()
            rows = parse_xml_bytes(xml_bytes, member.name)

            if rows:
                xml_files_with_articles += 1

            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                total_articles += 1

            if relevant_xml_files % 1000 == 0:
                print(
                    f"Relevant XML files read: {relevant_xml_files} — "
                    f"articles extracted: {total_articles}"
                )

    print(f"Archive: {ARCHIVE_PATH}")
    print(f"Archive members scanned: {total_members}")
    print(f"Archive members skipped: {skipped_members}")
    print(f"Relevant XML files read: {relevant_xml_files}")
    print(f"XML files with articles: {xml_files_with_articles}")
    print(f"Articles extracted: {total_articles}")
    print(f"Output written to: {OUTPUT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
