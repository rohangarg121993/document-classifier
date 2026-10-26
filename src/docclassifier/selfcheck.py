"""Self-check: can every category recognise a synthetic page built from its own definition?

Needs no labelled data. A category fails when its own page doesn't rank it first, or ranks it first by less than
`min_margin`; the runner-up then names the category it collides with.
"""

from __future__ import annotations

from dataclasses import replace

from docclassifier.classify import Category, CategorySet, classify
from docclassifier.ocr.models import PageText, Word
from docclassifier.settings import Settings

PAGE_WIDTH, PAGE_HEIGHT = 595.0, 842.0
DESCRIPTION_CHARS = 200


def synthetic_page(category: Category) -> PageText:
    """First synonym as the title at the top, positive phrases in the middle, a description excerpt at the bottom."""
    sections = [
        (80.0, category.synonyms[:1] or [category.name]),
        (PAGE_HEIGHT / 2, category.positive_phrases),
        (PAGE_HEIGHT - 120, [category.description[:DESCRIPTION_CHARS]]),
    ]
    words, lines = [], []
    for y, texts in sections:
        for row, text in enumerate(texts):
            line_y = y + 16 * row
            x = 72.0
            for token in text.split():
                words.append(Word(token, x, line_y - 6, x + 6 * len(token), line_y + 6))
                x += 6 * len(token) + 4
            lines.append(text)
    return PageText("\n".join(lines), words, PAGE_WIDTH, PAGE_HEIGHT, "native", 1)


def selfcheck(categories: CategorySet, settings: Settings, min_confidence: float) -> dict:
    # No fallback category, so a miss is never masked.
    settings = replace(settings, decision=replace(settings.decision, fallback_category_id=""))
    rows = []
    for category in categories:
        result = classify(synthetic_page(category), categories, settings)
        ranked = result.candidates_all
        rank = [c.category_id for c in ranked].index(category.category_id) + 1
        best_other = next(c for c in ranked if c.category_id != category.category_id)
        # The confidence the classifier reports for this page, credited only if the category actually won.
        confidence = _raw_confidence(ranked) if rank == 1 else 0.0
        rows.append(
            {
                "category_id": category.category_id,
                "rank": rank,
                "score": ranked[rank - 1].score,
                "confidence": confidence,
                "runner_up": best_other.category_id,
                "runner_up_score": best_other.score,
                "passed": rank == 1 and confidence >= min_confidence,
            }
        )
    collisions = sorted({tuple(sorted((r["category_id"], r["runner_up"]))) for r in rows if not r["passed"]})
    failed = sum(not r["passed"] for r in rows)
    return {
        "summary": {"categories": len(rows), "passed": len(rows) - failed, "failed": failed},
        "min_confidence": min_confidence,
        "collisions": [list(pair) for pair in collisions],
        "shared_synonyms": categories.warnings,
        "categories": rows,
    }


def _raw_confidence(ranked) -> float:
    top, second = ranked[0].score, ranked[1].score if len(ranked) > 1 else 0.0
    return round(top * (1 - (1 - top) / (1 - second)), 4) if second < 1 else 0.0


def format_report(report: dict) -> str:
    s = report["summary"]
    lines = [f"selfcheck: {s['passed']}/{s['categories']} categories pass (min confidence {report['min_confidence']})"]
    failing = [r for r in report["categories"] if not r["passed"]]
    if failing:
        lines.append("")
        lines.append(f"{'category':<10} {'rank':>4} {'score':>6} {'conf':>6}  runner-up")
        for r in sorted(failing, key=lambda r: r["confidence"]):
            lines.append(
                f"{r['category_id']:<10} {r['rank']:>4} {r['score']:>6.3f} {r['confidence']:>6.3f}"
                f"  {r['runner_up']} ({r['runner_up_score']:.3f})"
            )
        lines.append("")
        lines.append("collisions: " + ", ".join(" / ".join(pair) for pair in report["collisions"]))
    if report["shared_synonyms"]:
        lines.append("")
        lines.append(f"{len(report['shared_synonyms'])} synonym(s) are shared between categories:")
        lines.extend(f"  {warning}" for warning in report["shared_synonyms"])
    return "\n".join(lines)
