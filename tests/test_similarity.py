"""Similarity signal, exercised through `classify` only."""

import pytest

from docclassifier import classify, load_categories, load_settings

from conftest import HEADER
from test_classify import page_of

ROWS = [
    'GES01,Arbeitsunfähigkeit,"Ärztliche Bescheinigung über die Arbeitsunfähigkeit eines Mitarbeiters mit voraussichtlicher Dauer der Erkrankung.",AU-Bescheinigung,Krankmeldung,,Gesundheit',
    'ENT01,Gehaltsabrechnung,"Monatliche Abrechnung von Brutto- und Nettobezügen mit Steuern und Sozialversicherungsbeiträgen.",Lohnabrechnung,Entgeltabrechnung,,Entgelt',
    'BEW01,Bewerbung,"Bewerbungsschreiben mit Lebenslauf und Anlagen für eine ausgeschriebene Stelle.",Bewerbungsschreiben,Lebenslauf,,Bewerbung',
]


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def test_paraphrase_without_keywords_ranks_by_similarity(cats):
    page = page_of("Der Arzt bescheinigt die Arbeitsunfähigkeit, voraussichtliche Dauer der Erkrankung: zwei Wochen.")

    result = classify(page, cats, load_settings())

    assert [c.category_id for c in result.candidates_all][0] == "GES01"
    best = result.candidates_all[0]
    assert best.matched_synonyms == [] and best.matched_phrases == []
    assert best.similarity > max(c.similarity for c in result.candidates_all[1:])
