"""Scoring: keyword evidence plus profile similarity per page region, then the decision layer.

For each category and each region (top, middle, bottom thirds and the full page):
    region score = synonym_weight × synonym evidence + phrase_weight × phrase evidence + similarity_weight × similarity
The category score is the region-weighted average over regions that have enough text, minus the negative-phrase
penalty (counted once, on the full page), clipped to [0, 1].
"""

from __future__ import annotations

import logging
from functools import lru_cache

from docclassifier.classify.categories import Category, CategorySet
from docclassifier.classify.decision import decide
from docclassifier.classify.matching import MatchRules, PageMatcher
from docclassifier.classify.normalize import normalize
from docclassifier.classify.regions import REGIONS, split_regions
from docclassifier.classify.result import Candidate, ClassificationResult, KeywordMatch, RegionScore
from docclassifier.ocr.models import PageText
from docclassifier.settings import ClassifierSettings, Settings

log = logging.getLogger(__name__)


def classify(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult:
    cfg = settings.classifier
    rules = MatchRules(cfg.min_prefix_length, cfg.min_fuzzy_length, cfg.fuzzy_threshold)
    region_texts = {name: normalize(text) for name, text in split_regions(page).items()}
    # Regions with too little text are skipped; their weight is shared among the others.
    active = [r for r in REGIONS if len(region_texts[r].replace(" ", "")) >= cfg.min_region_chars] or ["full"]
    matchers = {r: PageMatcher(region_texts[r], rules) for r in active}
    similarities = dict(zip(active, categories.similarities([region_texts[r] for r in active])))

    ranked = [
        _score(category, index, categories, matchers, similarities, cfg)
        for index, category in enumerate(categories)
    ]
    # Highest score first; sort is stable, so ties keep CSV order.
    ranked.sort(key=lambda c: -c.score)

    full_text = region_texts["full"]
    result = decide(
        ranked, len(full_text.replace(" ", "")), cfg.top_n, categories, settings.decision, page.handwriting_suspected
    )
    # IDs and scores only: page text is personal data and must never reach the logs (ADR-0001).
    log.info(
        "page %s -> %s (%s, confidence %.3f; top: %s)",
        page.page_number, result.category_id, result.reason or result.status, result.confidence,
        ", ".join(f"{c.category_id}={c.score:.3f}" for c in result.candidates),
    )
    return result


def _score(
    category: Category,
    index: int,
    categories: CategorySet,
    matchers: dict[str, PageMatcher],
    similarities: dict[str, list[float]],
    cfg: ClassifierSettings,
) -> Candidate:
    weights = {r: category.region_weights.get(r, getattr(cfg, f"region_weight_{r}")) for r in matchers}
    total_weight = sum(weights.values()) or 1.0

    regions: dict[str, RegionScore] = {}
    for region, matcher in matchers.items():
        synonyms = _matches(category.synonyms, categories, matcher, cfg)
        phrases = _matches(category.positive_phrases, categories, matcher, cfg)
        synonym_score, phrase_score = _evidence(synonyms, cfg), _evidence(phrases, cfg)
        similarity = similarities[region][index]
        score = cfg.synonym_weight * synonym_score + cfg.phrase_weight * phrase_score + cfg.similarity_weight * similarity
        regions[region] = RegionScore(
            weight=round(weights[region] / total_weight, 4),
            score=round(score, 4),
            synonym_score=round(synonym_score, 4),
            phrase_score=round(phrase_score, 4),
            similarity=round(similarity, 4),
            matched_synonyms=synonyms,
            matched_phrases=phrases,
        )

    full_matcher = matchers.get("full") or next(iter(matchers.values()))
    negatives = _matches(category.negative_phrases, None, full_matcher, cfg)
    penalty = cfg.negative_penalty * len(negatives)
    weighted = sum(weights[r] * regions[r].score for r in regions) / total_weight
    full = regions.get("full") or next(iter(regions.values()))
    return Candidate(
        category_id=category.category_id,
        category_name=category.name,
        parent_category=category.parent,
        score=round(min(1.0, max(0.0, weighted - penalty)), 4),
        synonym_score=full.synonym_score,
        phrase_score=full.phrase_score,
        similarity=full.similarity,
        negative_penalty=round(penalty, 4),
        matched_synonyms=full.matched_synonyms,
        matched_phrases=full.matched_phrases,
        matched_negatives=negatives,
        regions=regions,
    )


def _matches(
    keywords: list[str], categories: CategorySet | None, matcher: PageMatcher, cfg: ClassifierSettings
) -> list[KeywordMatch]:
    """Distinct keyword hits. Specificity applies to positive keywords only (`categories` given)."""
    found: dict[str, KeywordMatch] = {}
    for keyword in keywords:
        key = _normalized_keyword(keyword)
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


@lru_cache(maxsize=8192)
def _normalized_keyword(keyword: str) -> str:
    # Keywords repeat across every page and region; page text is never cached.
    return normalize(keyword)


def _evidence(matches: list[KeywordMatch], cfg: ClassifierSettings) -> float:
    return min(1.0, sum(m.weight for m in matches) / cfg.keyword_cap)
