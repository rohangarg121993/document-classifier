"""Split a page into top / middle / bottom thirds plus the full page."""

from __future__ import annotations

from docclassifier.ocr.models import PageText

REGIONS = ("top", "middle", "bottom", "full")


def split_regions(page: PageText) -> dict[str, str]:
    """Region name → raw text. Thirds use each word's vertical centre relative to the page height;
    without word positions, the text's lines are split into thirds by count instead."""
    thirds: list[list[str]] = [[], [], []]
    if page.words and page.height > 0:
        for word in page.words:
            centre = (word.y0 + word.y1) / 2 / page.height
            thirds[min(2, max(0, int(centre * 3)))].append(word.text)
        texts = [" ".join(t) for t in thirds]
    else:
        lines = page.text.splitlines()
        n = len(lines)
        texts = ["\n".join(lines[i * n // 3 : (i + 1) * n // 3]) for i in range(3)]
    return {"top": texts[0], "middle": texts[1], "bottom": texts[2], "full": page.text}
