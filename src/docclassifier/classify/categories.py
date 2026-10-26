"""Category taxonomy loaded from CSV.

Accepts the files real editors produce: UTF-8 with or without BOM, or cp1252 (German Excel), and either
',' or ';' as the column delimiter. Inside a cell, list entries are always separated by ';'.
"""

from __future__ import annotations

import csv
import io
import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from docclassifier.classify.normalize import normalize

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = (
    "category_id",
    "category_name",
    "description",
    "synonyms",
    "positive_phrases",
    "negative_phrases",
    "parent_category",
)
REGIONS = ("top", "middle", "bottom", "full")


class CategoryFileError(ValueError):
    """The category CSV cannot be used. The message lists every problem found."""


@dataclass(frozen=True)
class Category:
    category_id: str
    name: str
    description: str
    synonyms: list[str]
    positive_phrases: list[str]
    negative_phrases: list[str]
    parent: str
    # Per-category region weight overrides from optional `weight_<region>` columns; missing regions use settings.
    region_weights: dict[str, float] = field(default_factory=dict)


class CategorySet(Sequence[Category]):
    """The loaded categories in CSV order, plus load warnings and keyword specificity weights."""

    def __init__(self, categories: list[Category], warnings: list[str]):
        self._categories = categories
        self.warnings = warnings
        listing = defaultdict(set)
        for c in categories:
            for keyword in c.synonyms + c.positive_phrases:
                listing[normalize(keyword)].add(c.category_id)
        self._listing_counts = {kw: len(ids) for kw, ids in listing.items()}

    def specificity(self, keyword: str) -> float:
        """1 / (1 + ln n), where n is how many categories list the keyword as synonym or positive phrase."""
        n = self._listing_counts.get(normalize(keyword), 1)
        return 1 / (1 + math.log(n))

    def __getitem__(self, index):
        return self._categories[index]

    def __len__(self) -> int:
        return len(self._categories)


def load_categories(path: str | Path) -> CategorySet:
    text = _decode(Path(path).read_bytes())
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    reader.fieldnames = [name.strip().lower() for name in reader.fieldnames or []]

    missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing:
        raise CategoryFileError(f"{path}: Missing required column(s): {', '.join(missing)}")

    errors: list[str] = []
    categories: list[Category] = []
    first_row_of: dict[str, int] = {}
    for row_number, row in enumerate(reader, start=2):  # row 1 is the header
        category = _parse_row(row, row_number, errors)
        if category is None:
            continue
        if category.category_id in first_row_of:
            errors.append(
                f"Duplicate category_id {category.category_id!r} in rows {first_row_of[category.category_id]} and {row_number}"
            )
            continue
        first_row_of[category.category_id] = row_number
        categories.append(category)

    if errors:
        raise CategoryFileError(f"{path}: {len(errors)} problem(s):\n" + "\n".join(f"  - {e}" for e in errors))

    warnings = _shared_synonym_warnings(categories)
    for warning in warnings:
        log.debug("%s", warning)
    if warnings:
        log.warning("%d synonym(s) are shared between categories; see CategorySet.warnings or debug logs", len(warnings))
    return CategorySet(categories, warnings)


def _decode(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    return text.replace("\r\n", "\n")


def _parse_row(row: dict[str, str | None], row_number: int, errors: list[str]) -> Category | None:
    category_id = (row["category_id"] or "").strip()
    if not category_id:
        errors.append(f"Row {row_number}: empty category_id")
        return None

    positives = _split(row["synonyms"]) + _split(row["positive_phrases"])
    negatives = _split(row["negative_phrases"])
    conflicts = sorted({normalize(k) for k in positives} & {normalize(k) for k in negatives})
    if conflicts:
        errors.append(f"{category_id} (row {row_number}): keyword(s) listed as both positive and negative: {', '.join(conflicts)}")

    region_weights = {}
    for region in REGIONS:
        raw = (row.get(f"weight_{region}") or "").strip()
        if not raw:
            continue
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            value = -1.0
        if value < 0:
            errors.append(f"{category_id} (row {row_number}): weight_{region} must be a number >= 0, got {raw!r}")
        else:
            region_weights[region] = value

    return Category(
        category_id=category_id,
        name=(row["category_name"] or "").strip(),
        description=(row["description"] or "").strip(),
        synonyms=_split(row["synonyms"]),
        positive_phrases=_split(row["positive_phrases"]),
        negative_phrases=negatives,
        parent=(row["parent_category"] or "").strip(),
        region_weights=region_weights,
    )


def _shared_synonym_warnings(categories: list[Category]) -> list[str]:
    owners = defaultdict(list)
    for c in categories:
        for synonym in dict.fromkeys(normalize(s) for s in c.synonyms):
            owners[synonym].append(c.category_id)
    return [
        f"Synonym {synonym!r} is listed in several categories: {', '.join(ids)}"
        for synonym, ids in owners.items()
        if len(ids) > 1
    ]


def _split(cell: str | None) -> list[str]:
    return [part.strip() for part in (cell or "").split(";") if part.strip()]
