"""Category taxonomy loaded from CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Category:
    category_id: str
    name: str
    description: str
    synonyms: list[str]
    positive_phrases: list[str]
    negative_phrases: list[str]
    parent: str


def load_categories(path: str | Path) -> list[Category]:
    """Read the category CSV (UTF-8, comma-delimited). List cells are separated by ';'."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [
            Category(
                category_id=row["category_id"].strip(),
                name=row["category_name"].strip(),
                description=row["description"].strip(),
                synonyms=_split(row["synonyms"]),
                positive_phrases=_split(row["positive_phrases"]),
                negative_phrases=_split(row["negative_phrases"]),
                parent=row["parent_category"].strip(),
            )
            for row in csv.DictReader(fh)
        ]


def _split(cell: str | None) -> list[str]:
    return [part.strip() for part in (cell or "").split(";") if part.strip()]
