"""Page extraction: embedded PDF text when present, otherwise offline OCR."""

from __future__ import annotations

from itertools import groupby
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from docclassifier.ocr import cache
from docclassifier.ocr.engines import OcrUnavailableError, create_engine
from docclassifier.ocr.models import PageText, Word
from docclassifier.settings import Settings

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
TIFF_SUFFIXES = {".tif", ".tiff"}
SUPPORTED_SUFFIXES = {".pdf"} | IMAGE_SUFFIXES | TIFF_SUFFIXES


class ExtractionError(Exception):
    """The page could not be extracted (bad file, unsupported type, page out of range, no OCR engine)."""


def extract_page(file: str | Path, page_number: int, settings: Settings) -> PageText:
    """Extract text and word positions from one page. `page_number` starts at 1."""
    path = Path(file)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"Unsupported file type {path.suffix!r}: {path.name}")
    if suffix == ".pdf":
        return _from_pdf(path, page_number, settings)
    return _cached_ocr(path, page_number, settings, lambda: _load_image(path, page_number))


def page_count(file: str | Path) -> int:
    path = Path(file)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"Unsupported file type {path.suffix!r}: {path.name}")
    try:
        if suffix == ".pdf":
            with pymupdf.open(path) as doc:
                return doc.page_count
        with Image.open(path) as image:
            return getattr(image, "n_frames", 1)
    except Exception as exc:
        raise ExtractionError(f"Cannot open {path.name}: {exc}") from exc


def _from_pdf(path: Path, page_number: int, settings: Settings) -> PageText:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # PyMuPDF raises several unrelated types for bad files
        raise ExtractionError(f"Cannot open {path.name}: {exc}") from exc
    with doc:
        _check_range(path, page_number, doc.page_count)
        page = doc[page_number - 1]
        if not settings.ocr.force_ocr:
            text = page.get_text("text", sort=True)
            if len("".join(text.split())) >= settings.ocr.min_native_chars:
                words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words", sort=True)]
                return PageText(text, words, page.rect.width, page.rect.height, "native", page_number)
        dpi = settings.ocr.dpi
        return _cached_ocr(path, page_number, settings, lambda: _render(page, dpi))


def _render(page: pymupdf.Page, dpi: int) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return Image.frombytes("L", (pix.width, pix.height), pix.samples)


def _cached_ocr(path: Path, page_number: int, settings: Settings, load_image) -> PageText:
    if not settings.cache.enabled:
        return _ocr(load_image(), page_number, settings)
    key = cache.cache_key(path, page_number, settings)
    page = cache.load(key, settings)
    if page is None:
        page = _ocr(load_image(), page_number, settings)
        cache.store(key, page, settings)
    return page


def _load_image(path: Path, page_number: int) -> Image.Image:
    try:
        image = Image.open(path)
    except Exception as exc:
        raise ExtractionError(f"Cannot open {path.name}: {exc}") from exc
    _check_range(path, page_number, getattr(image, "n_frames", 1))
    image.seek(page_number - 1)
    return image.copy()


def _ocr(image: Image.Image, page_number: int, settings: Settings) -> PageText:
    try:
        engine = create_engine(settings.ocr)
    except OcrUnavailableError as exc:
        raise ExtractionError(str(exc)) from exc
    image = ImageOps.grayscale(ImageOps.exif_transpose(image))
    rotate = engine.orientation(image)
    if rotate:
        # Tesseract reports the clockwise rotation that makes the text upright; PIL rotates counter-clockwise.
        image = image.rotate(-rotate, expand=True, fillcolor=255)
    words = engine.extract(image)
    lines = [" ".join(w.text for w in group) for _, group in groupby(words, key=lambda w: w.line)]
    return PageText("\n".join(lines), words, float(image.width), float(image.height), "ocr", page_number)


def _check_range(path: Path, page_number: int, count: int) -> None:
    if not 1 <= page_number <= count:
        raise ExtractionError(f"{path.name} has {count} page(s); page {page_number} does not exist")
