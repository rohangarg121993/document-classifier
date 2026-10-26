import pytest

from docclassifier import extract_page, load_settings
from docclassifier.ocr import ExtractionError


def test_native_pdf_text_with_word_positions(make_pdf):
    pdf = make_pdf([[(100, "Abmahnung wegen Verspätung")], [(700, "Seite zwei mit genug Text")]])

    page = extract_page(pdf, 2, load_settings())

    assert page.method == "native"
    assert page.page_number == 2
    assert "Seite zwei" in page.text
    assert [w.text for w in page.words] == ["Seite", "zwei", "mit", "genug", "Text"]
    assert page.height > 0 and page.width > 0
    # Bottom-of-page text has a large y coordinate (origin top-left).
    assert all(w.y0 > page.height / 2 for w in page.words)
    assert page.handwriting_suspected is False


def test_page_number_out_of_range(make_pdf):
    pdf = make_pdf([[(100, "nur eine Seite")]])

    with pytest.raises(ExtractionError, match="page 3"):
        extract_page(pdf, 3, load_settings())

    with pytest.raises(ExtractionError, match="page 0"):
        extract_page(pdf, 0, load_settings())


def test_unsupported_file_type(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ExtractionError, match="Unsupported"):
        extract_page(path, 1, load_settings())


def test_missing_tesseract_is_a_clear_error(make_pdf, tmp_path):
    from dataclasses import replace

    settings = load_settings()
    settings = replace(settings, ocr=replace(settings.ocr, force_ocr=True, tesseract_cmd=str(tmp_path / "nope.exe")))
    pdf = make_pdf([[(80, "Abmahnung wegen Pflichtverletzung")]])

    with pytest.raises(ExtractionError, match="Tesseract not found.*nope.exe"):
        extract_page(pdf, 1, settings)
