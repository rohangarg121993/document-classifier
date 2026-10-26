"""Page extraction. This version reads the text embedded in digital PDFs; OCR comes later."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from docclassifier.ocr.models import PageText, Word
from docclassifier.settings import Settings


class ExtractionError(Exception):
    """The page could not be extracted (bad file, unsupported type, page out of range)."""


def extract_page(file: str | Path, page_number: int, settings: Settings) -> PageText:
    """Extract text and word positions from one page. `page_number` starts at 1."""
    path = Path(file)
    if path.suffix.lower() != ".pdf":
        raise ExtractionError(f"Unsupported file type {path.suffix!r}: {path.name}")
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several unrelated types for bad files
        raise ExtractionError(f"Cannot open {path.name}: {exc}") from exc
    with doc:
        if not 1 <= page_number <= doc.page_count:
            raise ExtractionError(f"{path.name} has {doc.page_count} page(s); page {page_number} does not exist")
        page = doc[page_number - 1]
        words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words", sort=True)]
        return PageText(
            text=page.get_text("text", sort=True),
            words=words,
            width=page.rect.width,
            height=page.rect.height,
            method="native",
            page_number=page_number,
        )
