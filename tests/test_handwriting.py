"""Handwriting detection (OCR seam) and the confidence cap (classify seam)."""

import math
import random
from dataclasses import replace

import pytest
from PIL import Image, ImageDraw

from docclassifier import classify, extract_page, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import HEADER

LETTER = [(80 + 25 * i, "Abmahnung wegen Pflichtverletzung im Betrieb am Montag") for i in range(10)]


def scribble_page(path):
    """A4 at 200 DPI covered in cursive-like pen strokes: lots of ink, nothing OCR can read."""
    random.seed(7)
    image = Image.new("L", (1654, 2339), 255)
    draw = ImageDraw.Draw(image)
    for row in range(14):
        y0 = 200 + row * 130
        points = []
        for x in range(150, 1500, 6):
            y = y0 + 25 * math.sin(x / random.uniform(9, 15)) + 12 * math.sin(x / 41) + random.uniform(-4, 4)
            points.append((x, y))
        draw.line(points, fill=0, width=4)
    image.save(path)
    return path


@pytest.mark.tesseract
def test_scribbled_page_is_flagged(tmp_path):
    page = extract_page(scribble_page(tmp_path / "handwritten.png"), 1, load_settings())

    assert page.handwriting_suspected is True
    assert page.ocr_quality == "low"


@pytest.mark.tesseract
def test_printed_page_is_not_flagged(make_image):
    page = extract_page(make_image([LETTER]), 1, load_settings())

    assert page.handwriting_suspected is False
    assert page.ocr_quality == "ok"


ROWS = ["DIS01,Abmahnungen,x,Abmahnung; abgemahnt,Pflichtverletzung; Personalakte,,Disziplinar"]


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def strong_page(handwriting: bool) -> PageText:
    text = "Abmahnung abgemahnt Pflichtverletzung Personalakte"
    words = [Word(t, 72 + 120 * i, 60, 180 + 120 * i, 72, 40.0) for i, t in enumerate(text.split())]
    return PageText(text, words, 595, 842, "ocr", 1, ocr_quality="low", handwriting_suspected=handwriting)


def test_suspected_handwriting_caps_confidence(cats):
    settings = load_settings()

    normal = classify(strong_page(False), cats, settings)
    flagged = classify(strong_page(True), cats, settings)

    assert normal.status == "classified"
    assert flagged.confidence <= settings.decision.handwriting_confidence_cap
    assert flagged.status == "unclassified"
    assert flagged.candidates[0].category_id == "DIS01"  # evidence is still shown for the reviewer


def test_cap_is_configurable(cats):
    settings = load_settings()
    settings = replace(settings, decision=replace(settings.decision, handwriting_confidence_cap=1.0))

    assert classify(strong_page(True), cats, settings).status == "classified"
