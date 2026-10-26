"""Scoring: keyword evidence plus profile similarity on the full page, then the decision layer.

Page regions come in a later ticket.
"""

from __future__ import annotations

import logging

from docclassifier.classify.categories import Category, CategorySet
from docclassifier.classify.decision import decide
from docclassifier.classify.matching import MatchRules, PageMatcher
from docclassifier.classify.normalize import normalize
from docclassifier.classify.result import Candidate, ClassificationResult, KeywordMatch
from docclassifier.ocr.models import PageText
from docclassifier.settings import ClassifierSettings, Settings

log = logging.getLogger(__name__)


def classify(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult:
    cfg = settings.classifier
    text = normalize(page.text)
    matcher = PageMatcher(text, MatchRules(cfg.min_prefix_length, cfg.min_fuzzy_length, cfg.fuzzy_threshold))

    similarities = categories.similarity(page.text)
    ranked = [
        _score(category, categories, matcher, similarity, cfg)
        for category, similarity in zip(categories, similarities)
    ]
    # Highest score first; sort is stable, so ties keep CSV order.
    ranked.sort(key=lambda c: -c.score)

    result = decide(ranked, len(text.replace(" ", "")), cfg.top_n, categories, settings.decision)
    # IDs and scores only: page text is personal data and must never reach the logs (ADR-0001).
    log.info(
        "page %s -> %s (%s, confidence %.3f; top: %s)",
        page.page_number, result.category_id, result.reason or result.status, result.confidence,
        ", ".join(f"{c.category_id}={c.score:.3f}" for c in result.candidates),
    )
    return result


def _score(
    category: Category, categories: CategorySet, matcher: PageMatcher, similarity: float, cfg: ClassifierSettings
) -> Candidate:
    synonyms = _matches(category.synonyms, categories, matcher, cfg)
    phrases = _matches(category.positive_phrases, categories, matcher, cfg)
    negatives = _matches(category.negative_phrases, None, matcher, cfg)

    synonym_score = _evidence(synonyms, cfg)
    phrase_score = _evidence(phrases, cfg)
    penalty = cfg.negative_penalty * len(negatives)
    score = (
        cfg.synonym_weight * synonym_score
        + cfg.phrase_weight * phrase_score
        + cfg.similarity_weight * similarity
        - penalty
    )
    return Candidate(
        category_id=category.category_id,
        category_name=category.name,
        parent_category=category.parent,
        score=round(min(1.0, max(0.0, score)), 4),
        synonym_score=round(synonym_score, 4),
        phrase_score=round(phrase_score, 4),
        similarity=round(similarity, 4),
        negative_penalty=round(penalty, 4),
        matched_synonyms=synonyms,
        matched_phrases=phrases,
        matched_negatives=negatives,
    )


def _matches(
    keywords: list[str], categories: CategorySet | None, matcher: PageMatcher, cfg: ClassifierSettings
) -> list[KeywordMatch]:
    """Distinct keyword hits. Specificity applies to positive keywords only (`categories` given)."""
    found: dict[str, KeywordMatch] = {}
    for keyword in keywords:
        key = normalize(keyword)
        if key in found:
            continue
        kind = matcher.match(key)
        if kind is None:
            continue
        weight = categories.specificity(keyword) if categories is not None else 1.0
        if kind == "fuzzy":
            weight *= cfg.fuzzy_weight
        found[key] = KeywordMatch(keyword, kind, round(weight, 4))
    return list(found.values())


def _evidence(matches: list[KeywordMatch], cfg: ClassifierSettings) -> float:
    return min(1.0, sum(m.weight for m in matches) / cfg.keyword_cap)
