"""OCR quality and handwriting heuristics.

Tesseract reads print, not handwriting (ADR-0002). A page is suspected handwritten when much of its ink is not
covered by any confidently recognised word: pen strokes leave ink that OCR either skips or reads as junk.
"""

from __future__ import annotations

from typing import Literal

from PIL import Image, ImageDraw

from docclassifier.ocr.models import Word
from docclassifier.settings import OcrSettings

INK_LEVEL = 128  # grayscale values below this count as ink


def assess(image: Image.Image, words: list[Word], cfg: OcrSettings) -> tuple[Literal["ok", "low"], bool]:
    """Returns (ocr_quality, handwriting_suspected) for a grayscale page image and its OCR words."""
    ink = image.point(lambda v: 255 if v < INK_LEVEL else 0)
    total_ink = ink.histogram()[255]
    if total_ink / (image.width * image.height) < cfg.min_ink_ratio:
        return "ok", False  # (nearly) blank page: nothing to judge

    draw = ImageDraw.Draw(ink)
    for w in words:
        if (w.confidence or 0) >= cfg.handwriting_min_word_confidence:
            draw.rectangle((w.x0, w.y0, w.x1, w.y1), fill=0)
    unrecognised_share = ink.histogram()[255] / total_ink

    chars = sum(len(w.text) for w in words)
    mean_confidence = sum((w.confidence or 0) * len(w.text) for w in words) / chars if chars else 0.0

    handwriting = unrecognised_share >= cfg.handwriting_unrecognised_ink
    quality = "low" if handwriting or mean_confidence < cfg.low_quality_mean_confidence else "ok"
    return quality, handwriting
