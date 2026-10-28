"""Scoring: combine independent evidence per category into a strength, then hand over to the decision layer.

Evidence model (ADR-0003). Each signal removes part of the remaining doubt, so one strong signal plus
supporting ones gives a high strength, while a page without evidence stays near zero:

    strength = 1 - (1 - r_syn·synonyms)(1 - r_phr·phrases)(1 - r_sim·similarity)(1 - r_ex·examples)
               - penalty·negatives

- synonyms: document-type names; one hit is full evidence, weighted by where it appears (a title, i.e. top of
  the page or large print anywhere, counts fully);
- phrases: content clues; distinct hits weighted by position, specificity and fuzziness, capped;
- similarity: TF-IDF cosine to the category profile, relative to what a real matching page reaches; the top of
  the page (top third and large print) counts `similarity_top_share` once it holds more than a title;
- examples: TF-IDF cosine to the closest page a person validated for the category (ADR-0004).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from docclassifier.classify.categories import Category, CategorySet
from docclassifier.classify.decision import decide
from docclassifier.classify.matching import MatchRules, PageMatcher
from docclassifier.classify.normalize import normalize
from docclassifier.classify.regions import median_height, split_regions
from docclassifier.classify.result import Candidate, ClassificationResult, KeywordMatch
from docclassifier.ocr.models import PageText
from docclassifier.settings import ClassifierSettings, Settings

log = logging.getLogger(__name__)

POSITIONS = ("heading", "top", "middle", "bottom")


def classify(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult:
    cfg = settings.classifier
    rules = MatchRules(cfg.min_prefix_length, cfg.min_fuzzy_length, cfg.fuzzy_threshold)
    texts = {name: normalize(text) for name, text in split_regions(page, cfg.heading_ratio).items()}
    page_matcher = PageMatcher(texts["full"], rules)
    position_matchers = {p: PageMatcher(texts[p], rules) for p in POSITIONS}
    # The top of the page (top third and large print) says most about what a document is, as for a human reader.
    # A top holding only a title adds nothing the synonyms haven't counted, so then the whole page decides alone.
    top_text = f'{texts["heading"]} {texts["top"]}'
    full_similarities, top_similarities = categories.similarities([texts["full"], top_text])
    share = cfg.similarity_top_share if len(top_text.split()) >= cfg.similarity_top_min_words else 0.0
    similarities = [share * top + (1 - share) * full for full, top in zip(full_similarities, top_similarities)]
    example_similarities = [
        share * top + (1 - share) * full for full, top in zip(*categories.example_similarities(texts["full"], top_text))
    ]
    sizes = _word_sizes(page)
    title_level = _title_level(categories, page_matcher, position_matchers, cfg)

    ranked = [
        _score(
            category, categories, page_matcher, position_matchers, sizes, similarity, example_similarity,
            title_level, cfg,
        )
        for category, similarity, example_similarity in zip(categories, similarities, example_similarities)
    ]
    # Strongest first; sort is stable, so ties keep CSV order.
    ranked.sort(key=lambda c: -c.score)

    result = decide(
        ranked, len(texts["full"].replace(" ", "")), cfg.top_n, categories, settings.decision,
        page.handwriting_suspected,
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
    categories: CategorySet,
    page_matcher: PageMatcher,
    position_matchers: dict[str, PageMatcher],
    sizes: list[tuple[str, float]],
    similarity: float,
    example_similarity: float,
    title_level: float,
    cfg: ClassifierSettings,
) -> Candidate:
    # Synonyms are judged relative to the most title-like synonym on the page: running-text mentions count less
    # only when some document type actually is the title; on a page without one, the best-placed name counts fully.
    synonym_positions = {
        p: min(1.0, f / title_level) if title_level else f for p, f in _position_factors(category, cfg, "synonym").items()
    }
    phrase_positions = _position_factors(category, cfg, "phrase")

    # Synonyms are not discounted for being shared with a sibling: a shared title is still strong evidence
    # against unrelated categories, and the tie between siblings is resolved by the decision layer.
    synonyms = _matches(
        category.synonyms, None, synonym_positions, page_matcher, position_matchers, sizes, cfg,
        prefix_weight=cfg.synonym_prefix_weight,
    )
    phrases = _matches(
        category.positive_phrases, categories, phrase_positions, page_matcher, position_matchers, sizes, cfg
    )
    negatives = _matches(category.negative_phrases, None, None, page_matcher, position_matchers, sizes, cfg)

    synonym_evidence = min(1.0, sum(m.weight for m in synonyms) / cfg.synonym_cap)
    phrase_evidence = min(1.0, sum(m.weight for m in phrases) / cfg.phrase_cap)
    similarity_evidence = min(1.0, max(0.0, similarity) / cfg.similarity_full)
    floor = cfg.example_similarity_floor
    example_evidence = min(1.0, max(0.0, (example_similarity - floor) / (cfg.example_similarity_full - floor)))
    doubt = (
        (1 - cfg.synonym_reliability * synonym_evidence)
        * (1 - cfg.phrase_reliability * phrase_evidence)
        * (1 - cfg.similarity_reliability * similarity_evidence)
        * (1 - cfg.example_reliability * example_evidence)
    )
    penalty = cfg.negative_penalty * len(negatives)
    return Candidate(
        category_id=category.category_id,
        category_name=category.name,
        parent_category=category.parent,
        score=round(min(1.0, max(0.0, 1 - doubt - penalty)), 4),
        synonym_score=round(synonym_evidence, 4),
        phrase_score=round(phrase_evidence, 4),
        similarity=round(similarity, 4),
        example_similarity=round(example_similarity, 4),
        negative_penalty=round(penalty, 4),
        matched_synonyms=synonyms,
        matched_phrases=phrases,
        matched_negatives=negatives,
    )


def _position_factors(category: Category, cfg: ClassifierSettings, kind: str) -> dict[str, float]:
    """Settings per position; the CSV's weight_top/middle/bottom columns override them for one category."""
    return {p: category.region_weights.get(p, getattr(cfg, f"{kind}_position_{p}")) for p in POSITIONS}


def _title_level(
    categories: CategorySet, page_matcher: PageMatcher, position_matchers: dict[str, PageMatcher], cfg: ClassifierSettings
) -> float:
    """The best synonym position factor of any synonym on the page, from the global settings (0: no synonyms)."""
    factors = {p: getattr(cfg, f"synonym_position_{p}") for p in POSITIONS}
    best = 0.0
    for category in categories:
        for synonym in category.synonyms:
            key = _normalized_keyword(synonym)
            if page_matcher.match(key) is None:
                continue
            seen = [factors[p] for p in POSITIONS if position_matchers[p].match(key)]
            best = max(best, *(seen or [factors["middle"]]))  # across region boundaries: treat as running text
            if best >= 1.0:
                return best
    return best


def _word_sizes(page: PageText) -> list[tuple[str, float]]:
    """(normalised word, height relative to the page's median word height) for every positioned word."""
    typical = median_height(page.words)
    if not typical:
        return []
    return [(normalize(w.text), round((w.y1 - w.y0) / typical, 2)) for w in page.words]


def _size_of(key: str, sizes: list[tuple[str, float]]) -> float | None:
    """Largest relative print size among words that start the keyword; None without word positions."""
    first = key.split(" ", 1)[0]
    found = [size for word, size in sizes if word and (word.startswith(first) or first.startswith(word))]
    return max(found) if found else None


def _matches(
    keywords: list[str],
    categories: CategorySet | None,
    positions: dict[str, float] | None,
    page_matcher: PageMatcher,
    position_matchers: dict[str, PageMatcher],
    sizes: list[tuple[str, float]],
    cfg: ClassifierSettings,
    prefix_weight: float = 1.0,
) -> list[KeywordMatch]:
    """Distinct keyword hits on the page.

    `categories` given: weight by specificity (positive phrases). `positions` given: weight by the best
    position the keyword appears in; a keyword only found across a region boundary counts as "middle".
    `prefix_weight` scales hits found only at the start of a longer word.
    """
    found: dict[str, KeywordMatch] = {}
    for keyword in keywords:
        key = _normalized_keyword(keyword)
        if key in found:
            continue
        kind = page_matcher.match(key)
        if kind is None:
            continue
        weight = categories.specificity(keyword) if categories is not None else 1.0
        if kind == "fuzzy":
            weight *= cfg.fuzzy_weight
        elif kind == "prefix":
            weight *= prefix_weight
        position = "page"
        if positions is not None:
            seen = [p for p in POSITIONS if position_matchers[p].match(key)]
            position = max(seen, key=positions.__getitem__) if seen else "middle"
            weight *= positions[position]
        found[key] = KeywordMatch(keyword, kind, round(weight, 4), position, _size_of(key, sizes))
    return list(found.values())


@lru_cache(maxsize=8192)
def _normalized_keyword(keyword: str) -> str:
    # Keywords repeat across every page; page text is never cached.
    return normalize(keyword)
