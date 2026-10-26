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


def selfcheck(categories: CategorySet, settings: Settings, min_margin: float) -> dict:
    # Rank all categories: the decision threshold is irrelevant here, and no fallback should mask a miss.
    settings = replace(settings, decision=replace(settings.decision, fallback_category_id=""))
    rows = []
    for category in categories:
        ranked = classify(synthetic_page(category), categories, settings).candidates_all
        ids = [c.category_id for c in ranked]
        rank = ids.index(category.category_id) + 1
        own = ranked[rank - 1].score
        best_other = next(c for c in ranked if c.category_id != category.category_id)
        margin = round(own - best_other.score, 4)
        rows.append(
            {
                "category_id": category.category_id,
                "rank": rank,
                "score": own,
                "runner_up": best_other.category_id,
                "margin": margin,
                "passed": rank == 1 and margin >= min_margin,
            }
        )
    collisions = sorted({tuple(sorted((r["category_id"], r["runner_up"]))) for r in rows if not r["passed"]})
    failed = sum(not r["passed"] for r in rows)
    return {
        "summary": {"categories": len(rows), "passed": len(rows) - failed, "failed": failed},
        "min_margin": min_margin,
        "collisions": [list(pair) for pair in collisions],
        "categories": rows,
    }


def format_report(report: dict) -> str:
    s = report["summary"]
    lines = [f"selfcheck: {s['passed']}/{s['categories']} categories pass (min margin {report['min_margin']})"]
    failing = [r for r in report["categories"] if not r["passed"]]
    if failing:
        lines.append("")
        lines.append(f"{'category':<10} {'rank':>4} {'score':>6} {'margin':>7}  runner-up")
        for r in sorted(failing, key=lambda r: r["margin"]):
            lines.append(f"{r['category_id']:<10} {r['rank']:>4} {r['score']:>6.3f} {r['margin']:>7.3f}  {r['runner_up']}")
        lines.append("")
        lines.append("collisions: " + ", ".join(" / ".join(pair) for pair in report["collisions"]))
    return "\n".join(lines)
