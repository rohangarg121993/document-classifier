"""Scoring. This first version counts exact whole-word synonym matches on the full page."""

from __future__ import annotations

import logging

from docclassifier.classify.categories import Category
from docclassifier.classify.normalize import normalize
from docclassifier.classify.result import UNCLASSIFIED, Candidate, ClassificationResult
from docclassifier.ocr.models import PageText
from docclassifier.settings import Settings

log = logging.getLogger(__name__)


def classify(page: PageText, categories: list[Category], settings: Settings) -> ClassificationResult:
    # Padding with spaces turns whole-word matching into a substring test on normalised text.
    text = f" {normalize(page.text)} "
    cap = settings.classifier.keyword_cap

    scored = []
    for order, category in enumerate(categories):
        hits = sorted({kw for kw in map(normalize, category.synonyms) if kw and f" {kw} " in text})
        scored.append((min(1.0, len(hits) / cap), order, category, hits))
    # Highest score first; ties keep CSV order.
    scored.sort(key=lambda s: (-s[0], s[1]))

    candidates = [
        Candidate(c.category_id, c.name, c.parent, round(score, 4), hits)
        for score, _, c, hits in scored[: settings.classifier.top_n]
    ]
    best = candidates[0] if candidates else None
    if best is None or best.score == 0:
        result = ClassificationResult("unclassified", UNCLASSIFIED, None, None, 0.0, candidates)
    else:
        result = ClassificationResult(
            "classified", best.category_id, best.category_name, best.parent_category, best.score, candidates
        )
    # IDs and scores only: page text is personal data and must never reach the logs (ADR-0001).
    log.info(
        "page %s -> %s (confidence %.3f; top: %s)",
        page.page_number, result.category_id, result.confidence,
        ", ".join(f"{c.category_id}={c.score:.3f}" for c in candidates),
    )
    return result
