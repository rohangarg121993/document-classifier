"""Decision layer, exercised through `classify` with similarity off so strengths are hand-checkable.

With similarity off and every word at the top of the page:
    strength = 1 − (1 − 0.95·synonym evidence)(1 − 0.60·phrase evidence)
    synonym evidence = min(1, hits / 1), phrase evidence = min(1, hits / 3)
    confidence = s1 · (1 − (1 − s1) / (1 − s2))
"""

from dataclasses import replace

import pytest

from docclassifier import classify, load_categories, load_settings

from conftest import HEADER
from test_classify import page_of

ROWS = [
    "ZEU01,Zeugnis extern,x,Arbeitszeugnis; Endzeugnis,,,Zeugnisse",
    "ZEU05,Abschlusszeugnis,x,Abschlusszeugnis; Endzeugnis,,,Zeugnisse",
    "DIS01,Abmahnungen,x,Abmahnung; abgemahnt,Pflichtverletzung; Personalakte,,Disziplinar",
    "SON02,sonstiges,x,sonstiges,,,Sonstiges",
]
# DIS01 with a synonym and two phrases: 1 − 0.05 · (1 − 0.6·2/3) = 0.97
STRONG = "Abmahnung abgemahnt Pflichtverletzung Personalakte"
# DIS01 with one phrase only: 0.6 · 1/3 = 0.2 → confidence 0.2 · (1 − 0.8/1) = 0.04
WEAK = "Betreff: Personalakte vom Mai"


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def decide(text, cats, classifier=None, decision=None):
    settings = load_settings()
    settings = replace(
        settings,
        classifier=replace(settings.classifier, similarity_reliability=0, **(classifier or {})),
        decision=replace(settings.decision, **(decision or {})),
    )
    return classify(page_of(text), cats, settings)


def test_confidence_compares_doubt_of_winner_and_runner_up(cats):
    # Alone: runner-up strength 0 → 0.97 · (1 − 0.03/1) = 0.9409
    alone = decide(STRONG, cats)
    # ZEU01 gets a synonym hit (0.95) → 0.97 · (1 − 0.03/0.05) = 0.388
    contested = decide(STRONG + " Arbeitszeugnis", cats)

    assert alone.confidence == pytest.approx(0.9409, abs=1e-3)
    assert contested.confidence == pytest.approx(0.388, abs=1e-3)
    assert contested.candidates[0].category_id == "DIS01"


def test_low_confidence_is_unclassified_with_candidates(cats):
    result = decide(WEAK, cats)

    assert result.status == "unclassified"
    assert result.reason == "low_confidence"
    assert result.category_id == "UNCLASSIFIED"
    assert result.confidence == pytest.approx(0.04, abs=1e-3)
    assert [c.category_id for c in result.candidates][0] == "DIS01"
    assert len(result.candidates) == 3


def test_threshold_is_configurable(cats):
    result = decide(WEAK, cats, decision={"threshold": 0.01})

    assert result.status == "classified"
    assert result.reason is None
    assert result.category_id == "DIS01"


def test_nearly_empty_page_is_insufficient_text(cats):
    result = decide("Abmahnung", cats, decision={"threshold": 0.0})  # 9 characters < 20

    assert result.status == "unclassified"
    assert result.reason == "insufficient_text"
    assert result.category_id == "UNCLASSIFIED"


def test_confident_parent_when_siblings_tie(cats):
    # ZEU01 and ZEU05 both have a synonym hit → 0.95 each → child confidence 0.95 · (1 − 0.05/0.05) = 0
    # Parent "Zeugnisse" 0.95 against nothing → 0.95 · 0.95 = 0.9025
    result = decide("Endzeugnis Arbeitszeugnis Abschlusszeugnis", cats)

    assert result.status == "parent_only"
    assert result.reason == "low_confidence"
    assert result.category_id == "UNCLASSIFIED"
    assert result.parent_category == "Zeugnisse"
    assert result.confidence == pytest.approx(0.0, abs=1e-3)
    assert result.parent_confidence == pytest.approx(0.9025, abs=1e-3)


def test_classified_result_reports_parent_confidence(cats):
    result = decide(STRONG, cats)

    assert result.status == "classified"
    assert result.parent_category == "Disziplinar"
    assert result.parent_confidence == pytest.approx(0.9409, abs=1e-3)


def test_fallback_category_replaces_unclassified(cats):
    result = decide(WEAK, cats, decision={"fallback_category_id": "SON02"})

    assert result.status == "fallback"
    assert result.reason == "low_confidence"
    assert result.category_id == "SON02"
    assert result.category_name == "sonstiges"
    assert result.parent_category == "Sonstiges"


def test_unknown_fallback_category_is_rejected(cats):
    with pytest.raises(ValueError, match="fallback_category_id 'NOPE'"):
        decide(WEAK, cats, decision={"fallback_category_id": "NOPE"})


def test_ties_go_to_csv_order(cats):
    # "Endzeugnis" is a synonym of ZEU01 and ZEU05 alike; ZEU01 comes first in the CSV.
    result = decide("Endzeugnis Endzeugnis Endzeugnis", cats, decision={"threshold": 0.0})

    assert [c.category_id for c in result.candidates[:2]] == ["ZEU01", "ZEU05"]
    assert result.category_id == "ZEU01"
