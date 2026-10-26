"""Data passed from the OCR module to the classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Word:
    """One word with its bounding box in page coordinates (origin top-left)."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float | None = None  # 0-100 from OCR engines; None for native PDF text
    line: tuple[int, ...] | None = None  # OCR line identifier, used to rebuild line breaks


@dataclass(frozen=True)
class PageText:
    text: str
    words: list[Word]
    width: float
    height: float
    method: Literal["native", "ocr"]
    page_number: int
    ocr_quality: Literal["ok", "low"] | None = None
    handwriting_suspected: bool = False
    warnings: list[str] = field(default_factory=list)
