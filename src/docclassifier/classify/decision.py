"""The last step of every decision: a page left without a category may go to a configured fallback category."""

from __future__ import annotations

from dataclasses import replace

from docclassifier.classify.categories import CategorySet
from docclassifier.classify.result import UNCLASSIFIED, ClassificationResult
from docclassifier.settings import DecisionSettings


def with_fallback(result: ClassificationResult, categories: CategorySet, cfg: DecisionSettings) -> ClassificationResult:
    """`result`, or, when it names no category and `fallback_category_id` is set, that category instead."""
    if result.category_id != UNCLASSIFIED or not cfg.fallback_category_id:
        return result
    fallback = next((c for c in categories if c.category_id == cfg.fallback_category_id), None)
    if fallback is None:
        raise ValueError(f"fallback_category_id {cfg.fallback_category_id!r} is not in the category file")
    return replace(
        result, status="fallback", category_id=fallback.category_id, category_name=fallback.name,
        parent_category=fallback.parent,
    )
