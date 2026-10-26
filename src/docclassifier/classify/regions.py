"""Where on the page text appears: top / middle / bottom thirds, large-print headings, and the full page."""

from __future__ import annotations

from statistics import median

from docclassifier.ocr.models import PageText, Word

MIN_WORDS_FOR_HEADINGS = 5


def split_regions(page: PageText, heading_ratio: float = 1.4) -> dict[str, str]:
    """Region name → raw text.

    Thirds use each word's vertical centre relative to the page height; without word positions, the text's lines
    are split into thirds by count instead. "heading" holds words printed at least `heading_ratio` times taller
    than the page's median word, i.e. titles and labels in large print, wherever they sit.
    """
    thirds: list[list[str]] = [[], [], []]
    headings: list[str] = []
    if page.words and page.height > 0:
        typical = median_height(page.words)
        for word in page.words:
            centre = (word.y0 + word.y1) / 2 / page.height
            thirds[min(2, max(0, int(centre * 3)))].append(word.text)
            if typical and len(page.words) >= MIN_WORDS_FOR_HEADINGS and _height(word) >= heading_ratio * typical:
                headings.append(word.text)
        texts = [" ".join(t) for t in thirds]
    else:
        lines = page.text.splitlines()
        n = len(lines)
        texts = ["\n".join(lines[i * n // 3 : (i + 1) * n // 3]) for i in range(3)]
    return {"heading": " ".join(headings), "top": texts[0], "middle": texts[1], "bottom": texts[2], "full": page.text}


def median_height(words: list[Word]) -> float:
    heights = [h for h in map(_height, words) if h > 0]
    return median(heights) if heights else 0.0


def _height(word: Word) -> float:
    return word.y1 - word.y0
