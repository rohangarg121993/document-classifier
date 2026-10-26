"""Turn ranked candidates into a decision: category, confidence, or an explicit "don't know"."""

from __future__ import annotations

from dataclasses import replace

from docclassifier.classify.categories import CategorySet
from docclassifier.classify.result import UNCLASSIFIED, Candidate, ClassificationResult
from docclassifier.settings import DecisionSettings


def decide(
    ranked: list[Candidate],
    text_chars: int,
    top_n: int,
    categories: CategorySet,
    cfg: DecisionSettings,
    handwriting_suspected: bool = False,
) -> ClassificationResult:
    """`ranked` holds every category, best first. `text_chars` counts the page's non-space characters.

    Suspected handwriting caps the confidence (OCR text is unreliable), which normally sends the page to review.
    When `fallback_category_id` is set, any result without a category is mapped to that category.
    """
    cap = cfg.handwriting_confidence_cap if handwriting_suspected else 1.0
    result = _decide(ranked, text_chars, top_n, cfg, cap)
    if result.category_id != UNCLASSIFIED or not cfg.fallback_category_id:
        return result
    fallback = next((c for c in categories if c.category_id == cfg.fallback_category_id), None)
    if fallback is None:
        raise ValueError(f"fallback_category_id {cfg.fallback_category_id!r} is not in the category file")
    return replace(
        result, status="fallback", category_id=fallback.category_id, category_name=fallback.name,
        parent_category=fallback.parent,
    )


def _decide(
    ranked: list[Candidate], text_chars: int, top_n: int, cfg: DecisionSettings, cap: float
) -> ClassificationResult:
    candidates = ranked[:top_n]
    confidence = min(cap, _confidence([c.score for c in ranked], cfg))
    parent, parent_confidence = _best_parent(ranked, cfg)
    parent_confidence = min(cap, parent_confidence)

    if text_chars < cfg.min_text_chars:
        return _unclassified("insufficient_text", confidence, candidates, ranked)
    if not ranked or confidence < cfg.threshold:
        if parent is not None and parent_confidence >= cfg.threshold:
            # "Definitely Zeugnisse & Qualifikation, unsure which one."
            return ClassificationResult(
                status="parent_only", category_id=UNCLASSIFIED, category_name=None, parent_category=parent,
                confidence=confidence, candidates=candidates, reason="low_confidence",
                parent_confidence=parent_confidence, candidates_all=ranked,
            )
        return _unclassified("low_confidence", confidence, candidates, ranked)

    best = ranked[0]
    return ClassificationResult(
        status="classified", category_id=best.category_id, category_name=best.category_name,
        parent_category=best.parent_category, confidence=confidence, candidates=candidates,
        parent_confidence=parent_confidence, candidates_all=ranked,
    )


def _best_parent(ranked: list[Candidate], cfg: DecisionSettings) -> tuple[str | None, float]:
    """Each parent scores as its strongest child; the parent confidence uses the same formula as for children."""
    parent_scores: dict[str, float] = {}
    for c in ranked:  # best first, so the first child seen per parent is its strongest
        parent_scores.setdefault(c.parent_category, c.score)
    if not parent_scores:
        return None, 0.0
    best = next(iter(parent_scores))
    return best, _confidence(list(parent_scores.values()), cfg)


def _confidence(scores: list[float], cfg: DecisionSettings) -> float:
    """Winner strength × how much less doubt the winner leaves than the runner-up (doubt = 1 − strength).

    Two strong candidates that are nearly tied leave similar doubt, so confidence drops towards 0; a strong
    winner against a weak runner-up keeps almost all of its strength.
    """
    top = scores[0] if scores else 0.0
    second = scores[1] if len(scores) > 1 else 0.0
    if second >= 1.0:
        return 0.0
    return round(top * (1 - (1 - top) / (1 - second)), 4)


def _unclassified(reason, confidence, candidates, ranked) -> ClassificationResult:
    return ClassificationResult(
        status="unclassified", category_id=UNCLASSIFIED, category_name=None, parent_category=None,
        confidence=confidence, candidates=candidates, reason=reason, candidates_all=ranked,
    )
