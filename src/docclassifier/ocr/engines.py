"""OCR engines behind a small interface, so an offline handwriting engine can be added later (ADR-0002)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Protocol

import pytesseract
from PIL import Image

from docclassifier.ocr.models import Word
from docclassifier.settings import OcrSettings

DEFAULT_WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class OcrUnavailableError(RuntimeError):
    """The configured OCR engine cannot run on this machine."""


class OcrEngine(Protocol):
    def extract(self, image: Image.Image) -> list[Word]:
        """Words with boxes in image pixel coordinates, each with a 0-100 confidence."""


class TesseractEngine:
    def __init__(self, cmd: Path, languages: str):
        self._cmd = str(cmd)
        self._languages = languages

    def extract(self, image: Image.Image) -> list[Word]:
        pytesseract.pytesseract.tesseract_cmd = self._cmd
        data = pytesseract.image_to_data(image, lang=self._languages, output_type=pytesseract.Output.DICT)
        words = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            confidence = float(data["conf"][i])
            if not text or confidence < 0:  # -1 marks layout rows, not words
                continue
            left, top = data["left"][i], data["top"][i]
            words.append(
                Word(
                    text, left, top, left + data["width"][i], top + data["height"][i], confidence,
                    line=(data["block_num"][i], data["par_num"][i], data["line_num"][i]),
                )
            )
        return words

    def orientation(self, image: Image.Image) -> int:
        """Clockwise rotation in degrees that Tesseract's orientation detection suggests; 0 if unsure."""
        pytesseract.pytesseract.tesseract_cmd = self._cmd
        try:
            osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractError:  # e.g. too few characters to decide
            return 0
        return int(osd.get("rotate", 0))


def create_engine(settings: OcrSettings) -> OcrEngine:
    if settings.engine != "tesseract":
        raise OcrUnavailableError(f"Unknown OCR engine {settings.engine!r}; available: tesseract")
    return TesseractEngine(find_tesseract(settings), settings.languages)


def find_tesseract(settings: OcrSettings) -> Path:
    """Lookup order: settings → TESSERACT_CMD environment variable → PATH → default Windows install."""
    tried = []
    for source, value in (
        ("settings [ocr].tesseract_cmd", settings.tesseract_cmd),
        ("TESSERACT_CMD", os.environ.get("TESSERACT_CMD", "")),
        ("PATH", shutil.which("tesseract") or ""),
        ("default install", str(DEFAULT_WINDOWS_TESSERACT)),
    ):
        if not value:
            continue
        if Path(value).is_file():
            return Path(value)
        tried.append(f"{source}: {value}")
        if source.startswith("settings"):
            break  # an explicit setting that is wrong should fail loudly, not fall through
    raise OcrUnavailableError("Tesseract not found. Tried " + "; ".join(tried) + ". Install it or set TESSERACT_CMD.")
