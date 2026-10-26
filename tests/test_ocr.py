"""OCR through `extract_page`, on synthetic scans generated in the test. Needs the Tesseract binary."""

from dataclasses import replace

import pytest

from docclassifier import extract_page, load_settings
from docclassifier.ocr import ExtractionError

LETTER = [(80, "Abmahnung"), (140, "Sehr geehrter Herr Beispiel,"), (170, "wegen Ihrer Pflichtverletzung am 3. Mai.")]

pytestmark = pytest.mark.tesseract


def ocr_settings(**overrides):
    settings = load_settings()
    return replace(settings, ocr=replace(settings.ocr, **overrides))


def test_image_only_pdf_page_is_ocred(make_scan):
    pdf = make_scan([[(80, "Deckblatt")], LETTER])

    page = extract_page(pdf, 2, load_settings())

    assert page.method == "ocr"
    assert "Abmahnung" in page.text
    assert "Pflichtverletzung" in page.text
    assert all(w.confidence is not None for w in page.words)
    title = next(w for w in page.words if w.text == "Abmahnung")
    assert title.y1 < page.height / 3  # positions come back in page coordinates


def test_png_jpg_and_multipage_tiff(make_image):
    png = make_image([LETTER], "scan.png")
    jpg = make_image([LETTER], "scan.jpg")
    tiff = make_image([[(80, "Deckblatt")], LETTER], "scan.tiff")

    for path, page_number in ((png, 1), (jpg, 1), (tiff, 2)):
        page = extract_page(path, page_number, load_settings())
        assert page.method == "ocr"
        assert "Abmahnung" in page.text, path.name


def test_tiff_page_out_of_range(make_image):
    tiff = make_image([LETTER, LETTER], "scan.tif")

    with pytest.raises(ExtractionError, match="page 3"):
        extract_page(tiff, 3, load_settings())


def test_force_ocr_on_digital_pdf(make_pdf):
    pdf = make_pdf([[(80, "Abmahnung wegen Pflichtverletzung am 3. Mai")]])

    assert extract_page(pdf, 1, load_settings()).method == "native"
    assert extract_page(pdf, 1, ocr_settings(force_ocr=True)).method == "ocr"


def test_rotated_scan_is_turned_upright(make_scan):
    lines = [(80 + 30 * i, "Abmahnung wegen Pflichtverletzung im Betrieb") for i in range(12)]
    pdf = make_scan([lines], rotate=90)

    page = extract_page(pdf, 1, load_settings())

    assert "Pflichtverletzung" in page.text
