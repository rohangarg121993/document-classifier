import logging

import pytest

from docclassifier import classify, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import REAL_CATEGORIES


def page_of(text: str) -> PageText:
    """A PageText with one line of words at the top of an A4 page."""
    words, x = [], 72.0
    for token in text.split():
        words.append(Word(token, x, 90.0, x + 8 * len(token), 102.0))
        x += 8 * len(token) + 4
    return PageText(text=text, words=words, width=595, height=842, method="native", page_number=1)


def test_synonym_on_page_picks_its_category(categories_csv):
    result = classify(page_of("Betreff: ABMAHNUNG wegen Fehlverhalten"), load_categories(categories_csv), load_settings())

    assert result.status == "classified"
    assert result.category_id == "DIS01"
    assert result.category_name == "Abmahnungen"
    assert result.parent_category == "Abmahnung & Disziplinar"
    assert 0 < result.confidence <= 1
    assert [m.keyword for m in result.candidates[0].matched_synonyms] == ["Abmahnung"]


def test_umlauts_and_sharp_s_are_normalised(categories_csv):
    # Keyword "Arbeitsunfähigkeitsbescheinigung" written with "ae" on the page.
    result = classify(page_of("Arbeitsunfaehigkeitsbescheinigung"), load_categories(categories_csv), load_settings())

    assert result.category_id == "GES01"


def test_inflected_compound_matches_long_synonym(categories_csv):
    # "abgemahnt" (9 characters) also matches at the start of "abgemahnten".
    result = classify(page_of("die abgemahnten Kollegen"), load_categories(categories_csv), load_settings())

    assert result.category_id == "DIS01"


@pytest.mark.xfail(strict=True, reason="needs the confidence threshold from the decision layer (#7)")
def test_no_evidence_is_unclassified(categories_csv):
    result = classify(page_of("Speiseplan der Kantine"), load_categories(categories_csv), load_settings())

    assert result.status == "unclassified"
    assert result.confidence == 0


def test_top_three_candidates_ordered_by_score(categories_csv):
    page = page_of("Zwischenzeugnis Abmahnung abgemahnt")
    result = classify(page, load_categories(categories_csv), load_settings())

    assert result.category_id == "DIS01"  # two distinct synonym hits beat one
    assert [c.category_id for c in result.candidates][:2] == ["DIS01", "ZEU03"]
    assert len(result.candidates) == 3


def test_logs_never_contain_page_text(categories_csv, caplog):
    secret = "Mustermann"
    with caplog.at_level(logging.DEBUG, logger="docclassifier"):
        classify(page_of(f"Abmahnung Herr {secret}"), load_categories(categories_csv), load_settings())

    assert caplog.records, "expected some log output"
    assert secret.lower() not in caplog.text.lower()


def test_real_taxonomy_loads():
    categories = load_categories(REAL_CATEGORIES)

    assert len(categories) == 144
    assert categories[0].category_id == "DIS01"
    assert "Abmahnung" in categories[0].synonyms
