"""Decision layer, exercised through `classify` with similarity off so scores are hand-checkable.

Keyword scores below: synonym evidence × 0.35 + phrase evidence × 0.25, evidence = min(1, hits / 3).
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


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def decide(text, cats, classifier=None, decision=None):
    settings = load_settings()
    settings = replace(
        settings,
        classifier=replace(settings.classifier, similarity_weight=0, **(classifier or {})),
        decision=replace(settings.decision, **(decision or {})),
    )
    return classify(page_of(text), cats, settings)


def test_confidence_blends_top_score_and_margin(cats):
    # DIS01: 0.35·2/3 + 0.25·2/3 = 0.40, nothing else matches → 0.7·0.40 + 0.3·0.40
    alone = decide("Abmahnung abgemahnt Pflichtverletzung Personalakte", cats)
    # ZEU01 now scores 0.35·1/3 ≈ 0.1167 → 0.7·0.40 + 0.3·(0.40 − 0.1167) = 0.365
    contested = decide("Abmahnung abgemahnt Pflichtverletzung Personalakte Arbeitszeugnis", cats)

    assert alone.confidence == pytest.approx(0.40, abs=1e-3)
    assert contested.confidence == pytest.approx(0.365, abs=1e-3)
    assert contested.category_id == "DIS01"


def test_low_confidence_is_unclassified_with_candidates(cats):
    # DIS01 alone: 0.35·1/3 ≈ 0.117 → confidence 0.117 < 0.30
    result = decide("Betreff: Abmahnung vom Mai", cats)

    assert result.status == "unclassified"
    assert result.reason == "low_confidence"
    assert result.category_id == "UNCLASSIFIED"
    assert result.confidence == pytest.approx(0.117, abs=1e-3)
    assert [c.category_id for c in result.candidates][0] == "DIS01"
    assert len(result.candidates) == 3


def test_threshold_is_configurable(cats):
    result = decide("Betreff: Abmahnung vom Mai", cats, decision={"threshold": 0.1})

    assert result.status == "classified"
    assert result.reason is None
    assert result.category_id == "DIS01"


def test_nearly_empty_page_is_insufficient_text(cats):
    result = decide("Abmahnung", cats, decision={"threshold": 0.0})  # 9 characters < 20

    assert result.status == "unclassified"
    assert result.reason == "insufficient_text"
    assert result.category_id == "UNCLASSIFIED"


def test_confident_parent_when_siblings_tie(cats):
    # keyword_cap 1: ZEU01 and ZEU05 both saturate synonyms → 0.35 each, margin 0
    # → child confidence 0.7·0.35 = 0.245 < 0.30, but parent "Zeugnisse" scores 0.35 against 0 → 0.35
    result = decide("Endzeugnis Arbeitszeugnis Abschlusszeugnis", cats, classifier={"keyword_cap": 1})

    assert result.status == "parent_only"
    assert result.reason == "low_confidence"
    assert result.category_id == "UNCLASSIFIED"
    assert result.parent_category == "Zeugnisse"
    assert result.confidence == pytest.approx(0.245, abs=1e-3)
    assert result.parent_confidence == pytest.approx(0.35, abs=1e-3)


def test_classified_result_reports_parent_confidence(cats):
    result = decide("Abmahnung abgemahnt Pflichtverletzung Personalakte", cats)

    assert result.status == "classified"
    assert result.parent_category == "Disziplinar"
    assert result.parent_confidence == pytest.approx(0.40, abs=1e-3)


def test_fallback_category_replaces_unclassified(cats):
    result = decide("Betreff: Abmahnung vom Mai", cats, decision={"fallback_category_id": "SON02"})

    assert result.status == "fallback"
    assert result.reason == "low_confidence"
    assert result.category_id == "SON02"
    assert result.category_name == "sonstiges"
    assert result.parent_category == "Sonstiges"


def test_unknown_fallback_category_is_rejected(cats):
    with pytest.raises(ValueError, match="fallback_category_id 'NOPE'"):
        decide("Betreff: Abmahnung vom Mai", cats, decision={"fallback_category_id": "NOPE"})


def test_ties_go_to_csv_order(cats):
    # "Endzeugnis" is a synonym of ZEU01 and ZEU05 alike; ZEU01 comes first in the CSV.
    result = decide("Endzeugnis Endzeugnis Endzeugnis", cats, decision={"threshold": 0.0})

    assert [c.category_id for c in result.candidates[:2]] == ["ZEU01", "ZEU05"]
    assert result.category_id == "ZEU01"
