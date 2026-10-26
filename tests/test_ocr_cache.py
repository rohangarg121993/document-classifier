"""OCR cache, observed through `extract_page`: after a first OCR run, Tesseract is made unavailable.
A cache hit still returns the page; a miss has to run OCR and therefore fails."""

from dataclasses import replace

import pytest

from docclassifier import extract_page, load_settings
from docclassifier.ocr import ExtractionError

pytestmark = pytest.mark.tesseract

LETTER = [(80, "Abmahnung"), (140, "wegen Ihrer Pflichtverletzung am 3. Mai.")]


def settings_for(cache_dir, **ocr_overrides):
    settings = load_settings()
    return replace(
        settings,
        ocr=replace(settings.ocr, **ocr_overrides),
        cache=replace(settings.cache, dir=str(cache_dir)),
    )


def test_second_extraction_is_served_from_cache(make_scan, tmp_path):
    pdf = make_scan([LETTER])
    first = extract_page(pdf, 1, settings_for(tmp_path / "cache"))

    again = extract_page(pdf, 1, settings_for(tmp_path / "cache", tesseract_cmd=str(tmp_path / "gone.exe")))

    assert again.method == "ocr"
    assert again.text == first.text
    assert again.words == first.words


def test_disabled_cache_always_runs_ocr(make_scan, tmp_path):
    pdf = make_scan([LETTER])
    settings = settings_for(tmp_path / "cache")
    extract_page(pdf, 1, replace(settings, cache=replace(settings.cache, enabled=False)))
    gone = settings_for(tmp_path / "cache", tesseract_cmd=str(tmp_path / "gone.exe"))

    with pytest.raises(ExtractionError, match="Tesseract not found"):
        extract_page(pdf, 1, replace(gone, cache=replace(gone.cache, enabled=False)))


def test_changed_file_contents_miss_the_cache(make_scan, tmp_path):
    pdf = make_scan([LETTER])
    extract_page(pdf, 1, settings_for(tmp_path / "cache"))
    make_scan([[(80, "Zwischenzeugnis")]])  # same file name, new contents

    with pytest.raises(ExtractionError, match="Tesseract not found"):
        extract_page(pdf, 1, settings_for(tmp_path / "cache", tesseract_cmd=str(tmp_path / "gone.exe")))


def test_changed_ocr_settings_miss_the_cache(make_scan, tmp_path):
    pdf = make_scan([LETTER])
    extract_page(pdf, 1, settings_for(tmp_path / "cache"))

    with pytest.raises(ExtractionError, match="Tesseract not found"):
        extract_page(pdf, 1, settings_for(tmp_path / "cache", dpi=200, tesseract_cmd=str(tmp_path / "gone.exe")))


def test_default_cache_location_is_project_local(make_scan, tmp_path):
    # Tests run with the temp dir as working directory, standing in for the project root.
    extract_page(make_scan([LETTER]), 1, load_settings())

    assert any((tmp_path / ".cache" / "ocr").rglob("*.json"))
