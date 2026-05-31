#!/usr/bin/env python3
"""
NormDef-FR annotation review interface.

This script provides a simple Tkinter graphical interface to validate
draft definition candidates one by one.

Input:
    data/annotation/annotation_batch_v0_2_draft_definitions_strict.jsonl

Output:
    data/annotation/annotation_batch_v0_2_reviewed.jsonl
    data/annotation/annotation_batch_v0_2_review_progress.json

Usage:
    python scripts/review_draft_definitions_gui.py

Manual labels:
    - valid_definition
    - partial
    - invalid
    - unsure

Workflow:
    1. Read the source metadata, raw_body, term_candidate, definition_candidate.
    2. Choose a manual_label.
    3. Fill/correct gold_term and gold_definition when needed.
    4. Click Save & Next.
    5. The script autosaves progress after every item.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_draft_definitions_strict.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_reviewed.jsonl"
PROGRESS_FILE = PROJECT_ROOT / "data" / "annotation" / "annotation_batch_v0_5_review_progress.json"

VALID_LABELS = ["valid_definition", "partial", "invalid", "unsure"]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records."""
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}\n"
            "Run scripts/draft_extract_definitions_from_batch_strict.py first."
        )

    rows: list[dict[str, Any]] = []

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

            if isinstance(row, dict):
                rows.append(row)

    return rows


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Save all rows as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_progress() -> int:
    """Load last index from progress file."""
    if not PROGRESS_FILE.exists():
        return 0

    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0

    index = data.get("current_index", 0)
    if isinstance(index, int) and index >= 0:
        return index

    return 0


def save_progress(index: int) -> None:
    """Save current index."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps({"current_index": index}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_gold_term(term: str) -> str:
    """Small helper for suggested gold term."""
    term = term.strip()

    # Optional gentle normalization for French articles.
    for prefix in ["L'", "l'", "Le ", "La ", "Les ", "Un ", "Une ", "Des "]:
        if term.startswith(prefix) and len(term) > len(prefix) + 2:
            return term[len(prefix):].strip()

    return term


class ReviewApp:
    def __init__(self, root: tk.Tk, rows: list[dict[str, Any]]):
        self.root = root
        self.rows = rows
        self.index = min(load_progress(), max(len(rows) - 1, 0))

        self.root.title("NormDef-FR — Validation des définitions brouillon")
        self.root.geometry("1200x820")

        self.label_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")

        self._build_ui()
        self.load_current()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Top frame
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=8)

        self.progress_label = tk.Label(top, text="", font=("Arial", 12, "bold"))
        self.progress_label.pack(side="left")

        tk.Button(top, text="⟵ Previous", command=self.previous_item).pack(side="right", padx=4)
        tk.Button(top, text="Next ⟶", command=self.next_item_without_save).pack(side="right", padx=4)
        tk.Button(top, text="Save & Next", command=self.save_and_next, bg="#d9ead3").pack(side="right", padx=4)
        tk.Button(top, text="Save", command=self.save_current, bg="#fff2cc").pack(side="right", padx=4)

        # Metadata frame
        meta = tk.LabelFrame(self.root, text="Métadonnées")
        meta.pack(fill="x", padx=10, pady=5)

        self.meta_text = tk.Text(meta, height=5, wrap="word")
        self.meta_text.pack(fill="x", padx=5, pady=5)
        self.meta_text.configure(state="disabled")

        # Main content frame
        content = tk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=10, pady=5)

        left = tk.Frame(content)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        right = tk.Frame(content)
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        raw_frame = tk.LabelFrame(left, text="raw_body — texte source à vérifier")
        raw_frame.pack(fill="both", expand=True)

        self.raw_text = tk.Text(raw_frame, height=12, wrap="word")
        self.raw_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.raw_text.configure(state="disabled")

        draft_frame = tk.LabelFrame(right, text="Extraction proposée par le script")
        draft_frame.pack(fill="both", expand=True)

        tk.Label(draft_frame, text="term_candidate").pack(anchor="w", padx=5)
        self.term_candidate_text = tk.Text(draft_frame, height=3, wrap="word")
        self.term_candidate_text.pack(fill="x", padx=5, pady=2)
        self.term_candidate_text.configure(state="disabled")

        tk.Label(draft_frame, text="definition_candidate").pack(anchor="w", padx=5)
        self.definition_candidate_text = tk.Text(draft_frame, height=8, wrap="word")
        self.definition_candidate_text.pack(fill="both", expand=True, padx=5, pady=2)
        self.definition_candidate_text.configure(state="disabled")

        # Annotation frame
        ann = tk.LabelFrame(self.root, text="Annotation manuelle")
        ann.pack(fill="x", padx=10, pady=5)

        label_frame = tk.Frame(ann)
        label_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(label_frame, text="manual_label:", font=("Arial", 10, "bold")).pack(side="left")

        for label in VALID_LABELS:
            tk.Radiobutton(
                label_frame,
                text=label,
                variable=self.label_var,
                value=label,
                command=self.on_label_change,
            ).pack(side="left", padx=8)

        buttons_frame = tk.Frame(ann)
        buttons_frame.pack(fill="x", padx=5, pady=3)

        tk.Button(buttons_frame, text="Copier proposition → Gold", command=self.copy_candidate_to_gold).pack(side="left", padx=4)
        tk.Button(buttons_frame, text="Gold vide", command=self.clear_gold_fields).pack(side="left", padx=4)
        tk.Button(buttons_frame, text="Marquer invalid", command=self.mark_invalid).pack(side="left", padx=4)
        tk.Button(buttons_frame, text="Marquer valid", command=self.mark_valid).pack(side="left", padx=4)
        tk.Button(buttons_frame, text="Marquer partial", command=self.mark_partial).pack(side="left", padx=4)
        tk.Button(buttons_frame, text="Marquer unsure", command=self.mark_unsure).pack(side="left", padx=4)

        gold_frame = tk.Frame(ann)
        gold_frame.pack(fill="x", padx=5, pady=5)

        # Gold term
        term_frame = tk.Frame(gold_frame)
        term_frame.pack(fill="x", pady=2)

        tk.Label(term_frame, text="gold_term:", width=18, anchor="w").pack(side="left")
        self.gold_term_entry = tk.Entry(term_frame)
        self.gold_term_entry.pack(side="left", fill="x", expand=True)

        # Gold definition
        tk.Label(gold_frame, text="gold_definition:", anchor="w").pack(fill="x")
        self.gold_definition_text = tk.Text(gold_frame, height=4, wrap="word")
        self.gold_definition_text.pack(fill="x", pady=2)

        # Scope and type
        lower_gold = tk.Frame(gold_frame)
        lower_gold.pack(fill="x", pady=2)

        tk.Label(lower_gold, text="gold_scope_label:", width=18, anchor="w").pack(side="left")
        self.gold_scope_label_entry = tk.Entry(lower_gold, width=18)
        self.gold_scope_label_entry.pack(side="left", padx=(0, 12))

        tk.Label(lower_gold, text="gold_inferred_scope:", width=20, anchor="w").pack(side="left")
        self.gold_inferred_scope_entry = tk.Entry(lower_gold, width=18)
        self.gold_inferred_scope_entry.pack(side="left", padx=(0, 12))

        tk.Label(lower_gold, text="gold_definition_type:", width=20, anchor="w").pack(side="left")
        self.gold_definition_type_entry = tk.Entry(lower_gold, width=24)
        self.gold_definition_type_entry.pack(side="left")

        # Notes
        tk.Label(gold_frame, text="correction_notes:", anchor="w").pack(fill="x")
        self.notes_text = tk.Text(gold_frame, height=3, wrap="word")
        self.notes_text.pack(fill="x", pady=2)

        # Status bar
        status = tk.Frame(self.root)
        status.pack(fill="x", padx=10, pady=5)

        self.status_label = tk.Label(status, textvariable=self.status_var, anchor="w", fg="blue")
        self.status_label.pack(side="left", fill="x", expand=True)

        tk.Button(status, text="Export reviewed JSONL", command=self.export_all).pack(side="right", padx=4)

        # Keyboard shortcuts
        self.root.bind("<Control-s>", lambda event: self.save_current())
        self.root.bind("<Control-Return>", lambda event: self.save_and_next())
        self.root.bind("<Left>", lambda event: self.previous_item())
        self.root.bind("<Right>", lambda event: self.next_item_without_save())
        self.root.bind("1", lambda event: self.set_label_and_copy("valid_definition"))
        self.root.bind("2", lambda event: self.set_label_and_copy("partial"))
        self.root.bind("3", lambda event: self.set_label_invalid())
        self.root.bind("4", lambda event: self.set_label_unsure())

    # ------------------------------------------------------------------
    # Data display
    # ------------------------------------------------------------------

    def current_row(self) -> dict[str, Any]:
        return self.rows[self.index]

    def set_text(self, widget: tk.Text, value: str, disabled: bool = True) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")
        if disabled:
            widget.configure(state="disabled")

    def get_text(self, widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip()

    def set_entry(self, entry: tk.Entry, value: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, value or "")

    def load_current(self) -> None:
        if not self.rows:
            messagebox.showerror("Erreur", "Aucune ligne à annoter.")
            self.root.destroy()
            return

        row = self.current_row()

        self.progress_label.configure(
            text=f"Instance {self.index + 1} / {len(self.rows)}"
        )

        meta_lines = [
            f"candidate_definition_id: {row.get('candidate_definition_id', '')}",
            f"source_code: {row.get('source_code', '')}",
            f"article_number: {row.get('article_number', '')}",
            f"pattern: {row.get('pattern', '')} | noise_risk: {row.get('noise_risk', '')} | stratum: {row.get('sampling_stratum', '')}",
            f"source_file: {row.get('source_file', '')}",
        ]

        self.meta_text.configure(state="normal")
        self.meta_text.delete("1.0", "end")
        self.meta_text.insert("1.0", "\n".join(meta_lines))
        self.meta_text.configure(state="disabled")

        self.set_text(self.raw_text, str(row.get("raw_body") or ""))
        self.set_text(self.term_candidate_text, str(row.get("term_candidate") or ""))
        self.set_text(self.definition_candidate_text, str(row.get("definition_candidate") or ""))

        self.label_var.set(str(row.get("manual_label") or ""))

        self.set_entry(self.gold_term_entry, str(row.get("gold_term") or ""))
        self.set_text(self.gold_definition_text, str(row.get("gold_definition") or ""), disabled=False)
        self.set_entry(self.gold_scope_label_entry, str(row.get("gold_scope_label") or ""))
        self.set_entry(self.gold_inferred_scope_entry, str(row.get("gold_inferred_scope") or ""))
        self.set_entry(self.gold_definition_type_entry, str(row.get("gold_definition_type") or ""))
        self.set_text(self.notes_text, str(row.get("correction_notes") or ""), disabled=False)

        self.update_status()

    # ------------------------------------------------------------------
    # Annotation helpers
    # ------------------------------------------------------------------

    def on_label_change(self) -> None:
        label = self.label_var.get()

        if label == "valid_definition":
            # Do not overwrite existing gold fields unless they are empty.
            if not self.gold_term_entry.get().strip():
                self.copy_candidate_to_gold()
        elif label == "invalid":
            self.clear_gold_fields()

    def copy_candidate_to_gold(self) -> None:
        row = self.current_row()

        term = str(row.get("term_candidate") or "")
        definition = str(row.get("definition_candidate") or "")

        # Suggested normalization: remove leading French article from gold term.
        suggested_term = normalize_gold_term(term)

        self.set_entry(self.gold_term_entry, suggested_term)
        self.set_text(self.gold_definition_text, definition, disabled=False)

        self.set_entry(self.gold_scope_label_entry, str(row.get("scope_label") or "unspecified"))
        self.set_entry(self.gold_inferred_scope_entry, str(row.get("inferred_scope") or "article"))
        self.set_entry(self.gold_definition_type_entry, str(row.get("definition_type") or "explicit"))

    def clear_gold_fields(self) -> None:
        self.set_entry(self.gold_term_entry, "")
        self.set_text(self.gold_definition_text, "", disabled=False)
        self.set_entry(self.gold_scope_label_entry, "")
        self.set_entry(self.gold_inferred_scope_entry, "")
        self.set_entry(self.gold_definition_type_entry, "")

    def mark_valid(self) -> None:
        self.label_var.set("valid_definition")
        self.copy_candidate_to_gold()

    def mark_partial(self) -> None:
        self.label_var.set("partial")
        if not self.gold_term_entry.get().strip():
            self.copy_candidate_to_gold()

    def mark_invalid(self) -> None:
        self.label_var.set("invalid")
        self.clear_gold_fields()
        if not self.get_text(self.notes_text):
            self.set_text(self.notes_text, "Faux positif : pas une définition terme-définition.", disabled=False)

    def mark_unsure(self) -> None:
        self.label_var.set("unsure")
        if not self.get_text(self.notes_text):
            self.set_text(self.notes_text, "Cas ambigu à revoir.", disabled=False)

    def set_label_and_copy(self, label: str) -> None:
        self.label_var.set(label)
        self.copy_candidate_to_gold()

    def set_label_invalid(self) -> None:
        self.mark_invalid()

    def set_label_unsure(self) -> None:
        self.mark_unsure()

    # ------------------------------------------------------------------
    # Save / navigation
    # ------------------------------------------------------------------

    def save_current(self) -> None:
        row = self.current_row()

        row["manual_label"] = self.label_var.get() or None
        row["gold_term"] = self.gold_term_entry.get().strip() or None
        row["gold_definition"] = self.get_text(self.gold_definition_text) or None
        row["gold_scope_text"] = row.get("scope_text")
        row["gold_scope_label"] = self.gold_scope_label_entry.get().strip() or None
        row["gold_inferred_scope"] = self.gold_inferred_scope_entry.get().strip() or None
        row["gold_definition_type"] = self.gold_definition_type_entry.get().strip() or None
        row["correction_notes"] = self.get_text(self.notes_text) or None

        save_jsonl(OUTPUT_FILE, self.rows)
        save_progress(self.index)

        self.update_status(saved=True)

    def save_and_next(self) -> None:
        if not self.validate_current_before_next():
            return

        self.save_current()

        if self.index < len(self.rows) - 1:
            self.index += 1
            save_progress(self.index)
            self.load_current()
        else:
            messagebox.showinfo("Terminé", "Dernière instance atteinte. Tout est sauvegardé.")

    def validate_current_before_next(self) -> bool:
        label = self.label_var.get()

        if label not in VALID_LABELS:
            messagebox.showwarning(
                "Label manquant",
                "Choisis un manual_label avant de passer à l'instance suivante.",
            )
            return False

        if label in {"valid_definition", "partial"}:
            if not self.gold_term_entry.get().strip():
                messagebox.showwarning(
                    "gold_term manquant",
                    "Pour valid_definition ou partial, gold_term doit être rempli.",
                )
                return False

            if not self.get_text(self.gold_definition_text):
                messagebox.showwarning(
                    "gold_definition manquant",
                    "Pour valid_definition ou partial, gold_definition doit être remplie.",
                )
                return False

        if label == "partial" and not self.get_text(self.notes_text):
            messagebox.showwarning(
                "Note recommandée",
                "Pour partial, ajoute une courte correction_notes expliquant la correction.",
            )
            return False

        return True

    def previous_item(self) -> None:
        self.save_current()

        if self.index > 0:
            self.index -= 1
            save_progress(self.index)
            self.load_current()

    def next_item_without_save(self) -> None:
        self.save_current()

        if self.index < len(self.rows) - 1:
            self.index += 1
            save_progress(self.index)
            self.load_current()

    def export_all(self) -> None:
        self.save_current()
        save_jsonl(OUTPUT_FILE, self.rows)
        messagebox.showinfo("Export", f"Fichier sauvegardé :\n{OUTPUT_FILE}")

    def update_status(self, saved: bool = False) -> None:
        reviewed = sum(1 for row in self.rows if row.get("manual_label"))
        valid = sum(1 for row in self.rows if row.get("manual_label") == "valid_definition")
        partial = sum(1 for row in self.rows if row.get("manual_label") == "partial")
        invalid = sum(1 for row in self.rows if row.get("manual_label") == "invalid")
        unsure = sum(1 for row in self.rows if row.get("manual_label") == "unsure")

        prefix = "Sauvegardé. " if saved else ""

        self.status_var.set(
            f"{prefix}Annotés: {reviewed}/{len(self.rows)} | "
            f"valid: {valid} | partial: {partial} | invalid: {invalid} | unsure: {unsure}"
        )


def main() -> int:
    rows = load_jsonl(INPUT_FILE)

    root = tk.Tk()
    app = ReviewApp(root, rows)
    root.mainloop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
