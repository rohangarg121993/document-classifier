"""Realistic pages against the real taxonomy: correct pages must come out confident, ambiguous ones must not.

Layouts follow real letters: title in the top third, body in the middle, signature/footer at the bottom.
"""

import unicodedata

import pytest

from docclassifier import classify, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import REAL_CATEGORIES


def page(lines):
    """`lines` is a list of (y, text) in body print on an A4 page."""
    words = []
    for y, text in lines:
        x = 72.0
        for token in text.split():
            words.append(Word(token, x, y - 6, x + 8 * len(token), y + 6))
            x += 8 * len(token) + 4
    return PageText("\n".join(text for _, text in lines), words, 595.0, 842.0, "native", 1)

PAGES = {
    "warning letter": [
        (60, "Abmahnung"),
        (380, "Sehr geehrter Herr Beispiel, wegen Ihrer Pflichtverletzung am 3. Mai erteilen wir Ihnen eine Abmahnung."),
        (410, "Im Wiederholungsfall müssen Sie mit arbeitsrechtlichen Konsequenzen bis zur Kündigung rechnen."),
        (700, "Eine Kopie dieses Schreibens wird zur Personalakte genommen. Mit freundlichen Grüßen, Personalabteilung"),
    ],
    "interim reference": [
        (60, "Zwischenzeugnis"),
        (380, "Frau Beispiel ist seit dem 1. April 2019 in unserem Unternehmen als Sachbearbeiterin tätig."),
        (410, "Ihre Leistung und ihr Verhalten gegenüber Vorgesetzten und Kollegen waren stets einwandfrei."),
        (700, "Dieses Zwischenzeugnis wird auf ihren Wunsch erstellt."),
    ],
    "title and one generic line": [(60, "Zwischenzeugnis"), (400, "Bitte beachten Sie die Anlage."), (700, "Personalabteilung")],
    "dismissal mentioning an earlier warning": [
        (60, "Kündigung des Arbeitsverhältnisses"),
        (380, "Sehr geehrter Herr Beispiel, hiermit kündigen wir das mit Ihnen bestehende Arbeitsverhältnis fristgerecht zum 31. Dezember."),
        (410, "Bereits mit Abmahnung vom 3. Mai wurden Sie auf Ihre Pflichtverletzung hingewiesen."),
        (700, "Mit freundlichen Grüßen, Personalabteilung"),
    ],
    "degree certificate": [
        (60, "Urkunde"),
        (380, "Die Universität Musterstadt verleiht Frau Beispiel den akademischen Grad"),
        (410, "Master of Science nach bestandener Masterprüfung im Studiengang Informatik."),
        (700, "Musterstadt, den 30. September 2020  Der Präsident  Siegel"),
    ],
    "sibling title only": [(60, "Endzeugnis"), (400, "Hiermit bestätigen wir die Angaben."), (700, "Personalabteilung")],
    # Permit-style page: no letter title, type label in normal print at the bottom, umlauts stored decomposed (NFD)
    # as some PDFs do.
    "residence permit": [
        (60, "BUNDESREPUBLIK DEUTSCHLAND  FEDERAL REPUBLIC OF GERMANY"),
        (330, unicodedata.normalize("NFD", "Name / Surname  Vorname / Given names")),
        (360, unicodedata.normalize("NFD", "Staatsangehörigkeit / Nationality  Geburtsdatum / Date of birth")),
        (390, unicodedata.normalize("NFD", "Gültig bis / Valid until  Art des Titels / Type of permit")),
        (700, "Residence Permit"),
    ],
    "canteen menu": [
        (60, "Speiseplan Kantine"),
        (380, "Montag Gemüsesuppe, Dienstag Nudeln mit Tomatensoße, Mittwoch Fisch"),
        (700, "Guten Appetit"),
    ],
}


@pytest.fixture(scope="module")
def cats():
    return load_categories(REAL_CATEGORIES)


def run(name, cats):
    return classify(page(PAGES[name]), cats, load_settings())


@pytest.mark.parametrize(
    "name, category",
    [
        ("warning letter", "DIS01"),
        ("interim reference", "ZEU03"),
        ("title and one generic line", "ZEU03"),
        ("dismissal mentioning an earlier warning", "AUS05"),
        ("residence permit", "URK09"),
    ],
)
def test_clear_pages_are_confident(name, category, cats):
    result = run(name, cats)

    assert (result.status, result.category_id) == ("classified", category)
    assert result.confidence >= load_settings().decision.threshold


def test_page_with_taxonomy_overlap_is_classified_with_moderate_confidence(cats):
    # "Urkunde" is a synonym of both ZEU02 and URK08, so the runner-up is close.
    result = run("degree certificate", cats)

    assert (result.status, result.category_id) == ("classified", "ZEU02")
    assert 0.5 <= result.confidence < 0.8


def test_sibling_tie_falls_back_to_parent(cats):
    # "Endzeugnis" is a synonym of ZEU01 and ZEU05 alike.
    result = run("sibling title only", cats)

    assert result.status == "parent_only"
    assert result.parent_category == "Zeugnisse & Qualifikation"
    assert result.confidence < 0.1
    assert result.parent_confidence >= load_settings().decision.threshold


def test_unrelated_page_is_unclassified(cats):
    result = run("canteen menu", cats)

    assert result.status == "unclassified"
    assert result.confidence < 0.1
