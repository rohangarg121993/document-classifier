"""Title-first classification (ADR-0005): judge a page the way a person reads it.

Find the document's title, match it against the category synonyms, and decide on that. Document types named
elsewhere on the page ("…müssen Sie mit einer Kündigung rechnen") are mentions, not the page's identity.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from statistics import median

import snowballstemmer

from docclassifier.classify import context
from docclassifier.classify.categories import CategorySet
from docclassifier.classify.decision import with_fallback
from docclassifier.classify.normalize import normalize
from docclassifier.classify.regions import split_regions
from docclassifier.classify.result import UNCLASSIFIED, Candidate, ClassificationResult, KeywordMatch
from docclassifier.ocr.models import PageText, Word
from docclassifier.settings import Settings

# "Betreff", "Betreff:", "Betr.:" as a word of its own, not the start of "Betriebsstätten-Nr.".
_SUBJECT = re.compile(r"^\s*(betreff\b|betr\.)\s*:?\s*", re.IGNORECASE)
_SALUTATION = re.compile(r"^\s*(sehr geehrte|liebe[rs]?\b|hallo\b|guten tag\b)", re.IGNORECASE)
# Footer lines: company and bank details, the same on every letter of a sender.
_FOOTER = re.compile(
    r"\b(iban|bic|hrb|hra|amtsgericht|registergericht|gesch[aä]ftsf[uü]hr|ust-?id|steuernummer|vorstand|aufsichtsrat)\b",
    re.IGNORECASE,
)
log = logging.getLogger(__name__)
_DIGIT = re.compile(r"\d")
_STEMMER = snowballstemmer.stemmer("german")
# Shortest first part of a compound; shorter ones are prefixes (Ab-, Be-, Ver-, Ent-) that change the meaning.
MIN_COMPOUND_PART = 4
# A title in body print is told from running text by its length.
MAX_TITLE_WORDS = 8


@dataclass(frozen=True)
class Line:
    text: str
    y: float  # baseline, from the top
    height: float  # tallest word on the line


def classify(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult:
    result = with_fallback(_classify(page, categories, settings), categories, settings.decision)
    # IDs and scores only: page text, the title included, is personal data and must never reach the logs (ADR-0001).
    log.info(
        "page %s -> %s (%s, confidence %.3f; top: %s)",
        page.page_number, result.category_id, result.reason or result.status, result.confidence,
        ", ".join(f"{c.category_id}={c.score:.3f}" for c in result.candidates),
    )
    return result


def _classify(page: PageText, categories: CategorySet, settings: Settings) -> ClassificationResult:
    # The first title candidate that names a category is the title; a letterhead in large print names none.
    titles = title_candidates(page, settings.classifier.heading_ratio)
    if len(normalize(page.text).replace(" ", "")) < settings.decision.min_text_chars:
        return _unclassified("insufficient_text", [], titles[0] if titles else None)
    if learned := _like_a_validated_page(page, categories, settings, titles[0] if titles else None):
        return learned
    title, matches = (titles[0] if titles else None), {}
    for candidate in titles:
        if found := _title_matches(candidate, categories, settings.classifier.min_compound_length):
            title, matches = candidate, found
            break
    candidates = [
        Candidate(
            category_id=c.category_id, category_name=c.name, parent_category=c.parent, score=1.0,
            synonym_score=1.0, matched_synonyms=[KeywordMatch(keyword, "exact", 1.0, "heading")],
        )
        for c in categories
        if (keyword := matches.get(c.category_id))
    ]
    if not candidates and settings.context.enabled:
        return _by_content(page, categories, settings, title)
    family = {c.category_id for c in categories if c.parent in {m.parent_category for m in candidates}}
    if len(family) > 1 and settings.context.enabled:
        # The title names a kind of document; the body decides which one in that family: "Kündigung" by the
        # employee or the employer, "Arbeitsvertrag" fixed-term or not.
        return _by_content(page, categories, settings, title, among=family, named=matches)
    # Every category is ranked: the ones the title names first, the rest unscored in CSV order.
    ranked = candidates + [
        Candidate(category_id=c.category_id, category_name=c.name, parent_category=c.parent, score=0.0)
        for c in categories
        if c.category_id not in matches
    ]
    if len(candidates) != 1:
        return _unclassified("low_confidence", ranked, title, settings.classifier.top_n)
    return _classified(ranked, settings.classifier.title_match_confidence, page, settings, title)


def _like_a_validated_page(
    page: PageText, categories: CategorySet, settings: Settings, title: str | None
) -> ClassificationResult | None:
    """The category of a validated page (ADR-0004) this page nearly repeats: the same form or letter, filled in
    for another person. Letters are compared as written (character n-grams), the top of the page weighted more."""
    cfg = settings.classifier
    regions = split_regions(page, cfg.heading_ratio)
    top_text = f"{regions['heading']} {regions['top']}"
    share = cfg.similarity_top_share if len(top_text.split()) >= cfg.similarity_top_min_words else 0.0
    full, top = categories.example_similarities(regions["full"], top_text)
    similarities = [share * t + (1 - share) * f for f, t in zip(full, top)]
    best = max(range(len(similarities)), key=similarities.__getitem__, default=None)
    if best is None or similarities[best] < cfg.example_similarity:
        return None
    ranked = [
        Candidate(
            category_id=c.category_id, category_name=c.name, parent_category=c.parent,
            score=round(similarity, 4), example_similarity=round(similarity, 4),
        )
        for c, similarity in sorted(zip(categories, similarities), key=lambda pair: -pair[1])
    ]
    return _classified(ranked, cfg.example_confidence, page, settings, title)


def _by_content(
    page: PageText, categories: CategorySet, settings: Settings, title: str | None,
    among: set[str] | None = None, named: dict[str, str] | None = None,
) -> ClassificationResult:
    """Judge the content, by meaning and by the category's own phrases.

    score = meaning (cosine to the category definition) + phrase_weight × positive-phrase evidence
            − negative_weight × negative-phrase hits.
    Phrases match by word stems, so "Einvernehmen" counts for "einvernehmlich". Decide only on a clear lead.
    `among`: only these categories compete (the family the title named); the others are ranked after them.
    `named`: category_id → synonym, the categories the title itself names.
    """
    cfg = settings.context
    named = named or {}
    # Between siblings the title already settled the topic, so meaning barely differs; their phrases decide.
    phrase_weight = cfg.sibling_phrase_weight if among is not None else cfg.phrase_weight
    text = content(page, title)
    cosines = context.similarities(text, categories, cfg.model_dir)
    stems, title_stems = _stems(text), _stems(title or "")
    scored = []
    for category, cosine in zip(categories, cosines):
        phrases = [p for p in category.positive_phrases if _contains(stems, _stems(p))]
        negatives = [p for p in category.negative_phrases if _contains(stems, _stems(p))]
        phrase_evidence = min(1.0, len(phrases) / settings.classifier.phrase_cap)
        # A negative phrase in the title itself rules the category out: an "Ermahnung" is not titled "Abmahnung".
        excluded = any(_contains(title_stems, _stems(p)) for p in negatives)
        penalty = 1.0 if excluded else cfg.negative_weight * len(negatives)
        synonym = named.get(category.category_id)
        scored.append(Candidate(
            category_id=category.category_id, category_name=category.name, parent_category=category.parent,
            score=round(cosine + phrase_weight * phrase_evidence - penalty, 4),
            synonym_score=1.0 if synonym else 0.0,
            phrase_score=round(phrase_evidence, 4), similarity=round(cosine, 4), negative_penalty=round(penalty, 4),
            matched_synonyms=[KeywordMatch(synonym, "exact", 1.0, "heading")] if synonym else [],
            matched_phrases=[KeywordMatch(p, "stem", 1.0) for p in phrases],
            matched_negatives=[KeywordMatch(p, "stem", 1.0) for p in negatives],
        ))
    ranked = sorted(scored, key=lambda c: (among is not None and c.category_id not in among, -c.score))
    competing = [c for c in ranked if among is None or c.category_id in among]
    if len(named) == 1:
        own = next(c for c in competing if c.category_id in named)
        if competing[0].score - own.score < cfg.min_margin:
            # The title names this category; a sibling overrules it only when the body clearly fits it better.
            ranked.remove(own)
            return _classified([own, *ranked], settings.classifier.title_match_confidence, page, settings, title)
        return _classified(ranked, cfg.confidence, page, settings, title)
    margin = competing[0].score - competing[1].score if len(competing) > 1 else competing[0].score
    if margin < cfg.min_margin:
        result = _unclassified("low_confidence", ranked, title, settings.classifier.top_n)
        contenders = {c.parent_category for c in competing if competing[0].score - c.score < cfg.min_margin}
        if len(contenders) == 1:
            # Too close to call between siblings, but clearly that kind of document.
            return replace(
                result, status="parent_only", parent_category=competing[0].parent_category,
                parent_confidence=cfg.confidence,
            )
        return result
    return _classified(ranked, cfg.confidence, page, settings, title)


def _classified(
    ranked: list[Candidate], confidence: float, page: PageText, settings: Settings, title: str | None
) -> ClassificationResult:
    """The leader of `ranked` wins, unless the confidence falls below the threshold: suspected handwriting caps
    it, because OCR may have misread the very words that decided."""
    cfg = settings.decision
    if page.handwriting_suspected:
        confidence = min(confidence, cfg.handwriting_confidence_cap)
    if confidence < cfg.threshold:
        return replace(_unclassified("low_confidence", ranked, title, settings.classifier.top_n), confidence=confidence)
    best = ranked[0]
    return ClassificationResult(
        status="classified", category_id=best.category_id, category_name=best.category_name,
        parent_category=best.parent_category, confidence=confidence, candidates=ranked[: settings.classifier.top_n],
        candidates_all=ranked, title=title,
    )


def _unclassified(reason: str, ranked: list[Candidate], title: str | None, top_n: int = 0) -> ClassificationResult:
    return ClassificationResult(
        status="unclassified", category_id=UNCLASSIFIED, category_name=None, parent_category=None,
        confidence=0.0, candidates=ranked[:top_n] if top_n else ranked, reason=reason, candidates_all=ranked,
        title=title,
    )


def content(page: PageText, title: str | None) -> str:
    """What the page says: from the title down (the letterhead and address block sit above it), without the
    footer's company and bank details."""
    page_lines = [line.text for line in lines(page)]
    start = next((i for i, text in enumerate(page_lines) if title and title in text), 0)
    return "\n".join(text for text in page_lines[start:] if not _FOOTER.search(text))


def _stems(text: str) -> tuple[str, ...]:
    return tuple(_stem(word) for word in normalize(text).split())


@lru_cache(maxsize=65536)
def _stem(word: str) -> str:
    return _STEMMER.stemWord(word)


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def title_candidates(page: PageText, heading_ratio: float) -> list[str]:
    """Lines that may name the document, in the order a reader looks for them:
    1. a subject line marked "Betreff: …";
    2. (DIN 5008 letters) the line that leads into the salutation;
    3. lines in the upper half printed clearly larger than the text, tallest first (contracts, certificates;
       a letterhead lands here too, which is why the caller takes the first candidate that names a category);
    4. short lines without digits in the top third, top to bottom: a title in bold at the text size looks like
       this; a form's table rows carry amounts and numbers.
    """
    page_lines = lines(page)
    found = [_SUBJECT.sub("", line.text).strip() for line in page_lines if _SUBJECT.match(line.text)]
    found += [page_lines[i - 1].text for i, line in enumerate(page_lines) if i and _SALUTATION.match(line.text)][:1]
    typical = median(w.y1 - w.y0 for w in page.words) if page.words else 0.0
    if typical:
        large = [l for l in page_lines if l.y < page.height / 2 and l.height >= heading_ratio * typical]
        found += [l.text for l in sorted(large, key=lambda l: (-l.height, l.y))]
    short = [l for l in page_lines if len(l.text.split()) <= MAX_TITLE_WORDS and not _DIGIT.search(l.text)]
    found += [l.text for l in short if l.y < page.height / 3]
    found += [l.text for l in short]
    return list(dict.fromkeys(found))


def lines(page: PageText) -> list[Line]:
    """The page's words regrouped into lines, top to bottom: words share a line when their baselines align."""
    rows: dict[float, list[Word]] = {}
    for word in page.words:
        rows.setdefault(round(word.y1), []).append(word)
    return [
        Line(" ".join(w.text for w in sorted(row, key=lambda w: w.x0)), y, max(w.y1 - w.y0 for w in row))
        for y, row in sorted(rows.items())
    ]


def _title_matches(title: str, categories: CategorySet, min_compound_length: int) -> dict[str, str]:
    """category_id → its longest synonym that names the title: as whole words, or (one word of at least
    `min_compound_length` letters) as the last part of a compound, "Verhaltensabmahnung" for "Abmahnung".
    The part in front must be a word of its own (MIN_COMPOUND_PART letters): "Abrechnung" is not a Rechnung.

    A match inside another category's longer match is dropped: "Zwischenzeugnis" names a Zwischenzeugnis,
    not just any Zeugnis.
    """
    normalized = normalize(title)
    padded, words = f" {normalized} ", normalized.split()
    found: dict[str, tuple[str, str]] = {}  # category_id → (normalised key, synonym as listed)
    for category in categories:
        for synonym in category.synonyms:
            key = normalize(synonym)
            compound = " " not in key and len(key) >= min_compound_length and any(
                w.endswith(key) and len(w) - len(key) >= MIN_COMPOUND_PART for w in words
            )
            if (f" {key} " in padded or compound) and len(key) > len(found.get(category.category_id, ("",))[0]):
                found[category.category_id] = (key, synonym)
    return {
        cid: synonym
        for cid, (key, synonym) in found.items()
        if not any(key != other and key in other for other, _ in found.values())
    }
