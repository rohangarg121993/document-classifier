"""Feedback store: pages a person validated in a review file, so later runs can use them (ADR-0004).

`learn` reads a corrected review file and stores each labelled page under a fingerprint of its normalised text;
`validated` returns the stored label when the same page comes back, whatever the file is called now, and
`with_examples` adds every validated page as an example of its category, so pages like it score higher.
Entries hold no file names, but they are derived from page text and count as personal data: the store lives in
a git-ignored directory and stays on this machine (ADR-0001).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from docclassifier.classify import CategorySet, ClassificationResult
from docclassifier.classify.normalize import normalize
from docclassifier.classify.regions import split_regions
from docclassifier.ocr import ExtractionError, extract_page
from docclassifier.ocr.models import PageText
from docclassifier.settings import Settings


def learn(labels: Iterable[tuple[Path, int, str]], settings: Settings) -> tuple[int, list[str]]:
    """Store every (file, page, expected) label. Returns (pages learned, problems)."""
    learned, problems = 0, []
    for file, page_number, expected in labels:
        try:
            page = extract_page(file, page_number, settings)
        except ExtractionError as exc:
            problems.append(f"{file} p{page_number}: {exc}")
            continue
        key = _fingerprint(page)
        if key is None:
            problems.append(f"{file} p{page_number}: no text, nothing to learn")
            continue
        entry = _entry(key, settings)
        entry.parent.mkdir(parents=True, exist_ok=True)
        regions = split_regions(page, settings.classifier.heading_ratio)
        top = normalize(f"{regions['heading']} {regions['top']}")
        data = {"category_id": expected, "text": normalize(page.text), "top": top}
        entry.write_text(json.dumps(data), encoding="utf-8")
        learned += 1
    return learned, problems


def with_examples(categories: CategorySet, settings: Settings) -> CategorySet:
    """`categories` plus every stored page as an example of its validated category."""
    if not settings.feedback.enabled:
        return categories
    examples = []
    for entry in sorted(Path(settings.feedback.dir).glob("*/*.json")):
        data = json.loads(entry.read_text(encoding="utf-8"))
        examples.append((data["category_id"], data["text"], data.get("top", "")))
    return categories.with_examples(examples)


def validated(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult | None:
    """The label a person gave this page before, or None. Labels no longer in the taxonomy are ignored."""
    if not settings.feedback.enabled:
        return None
    key = _fingerprint(page)
    entry = _entry(key, settings) if key else None
    if entry is None or not entry.is_file():
        return None
    category_id = json.loads(entry.read_text(encoding="utf-8"))["category_id"]
    category = next((c for c in categories if c.category_id == category_id), None)
    if category is None:
        return None
    return ClassificationResult(
        status="validated", category_id=category.category_id, category_name=category.name,
        parent_category=category.parent, confidence=1.0, candidates=[],
    )


def _fingerprint(page: PageText) -> str | None:
    # Normalised text, so a re-scan with different whitespace or umlaut encoding still matches.
    text = normalize(page.text)
    return hashlib.sha256(text.encode()).hexdigest() if text else None


def _entry(key: str, settings: Settings) -> Path:
    return Path(settings.feedback.dir) / key[:2] / f"{key}.json"
