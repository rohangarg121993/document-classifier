"""Keyword rules from the spec, exercised through `classify` only."""

from dataclasses import replace

import pytest

from docclassifier import classify, load_categories, load_settings

from conftest import HEADER
from test_classify import page_of

ROWS = [
    # id, name, description, synonyms, positive phrases, negatives, parent
    "DIS01,Abmahnungen,x,Abmahnung; abgemahnt,Pflichtverletzung; Personalakte; arbeitsrechtliche Konsequenzen,Ermahnung,Disziplinar",
    "AZF01,ATZ Checkliste,x,ATZ,Checkliste; Altersteilzeit,,Arbeitszeit",
    "FAM07,Mutterschutz Checkliste,x,Mutterschutz,Checkliste; Schutzfrist,,Familie",
    "BAV07,Pensionsplan P3,x,P3,Pensionsplan,,Altersversorgung",
    "VPF01,Datenschutz,x,Datenschutzerklaerung,Vertraulichkeit,,Verpflichtungen",
]


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def run(text, cats, **classifier_overrides):
    """Classify with similarity switched off, so scores reflect keyword evidence only."""
    settings = load_settings()
    classifier = replace(settings.classifier, similarity_reliability=0, **classifier_overrides)
    return classify(page_of(text), cats, replace(settings, classifier=classifier))


def candidate(result, category_id):
    return next(c for c in result.candidates_all if c.category_id == category_id)


def test_synonyms_count_more_than_phrases(cats):
    # One synonym hit for AZF01 vs one phrase hit for DIS01.
    result = run("ATZ Personalakte", cats)

    assert candidate(result, "AZF01").score > candidate(result, "DIS01").score


def test_compound_prefix_match_for_long_keywords(cats):
    result = run("Abmahnungsschreiben vom 3. Mai", cats)

    best = result.candidates[0]
    assert best.category_id == "DIS01"
    assert [(m.keyword, m.kind) for m in best.matched_synonyms] == [("Abmahnung", "prefix")]


def test_short_keywords_are_whole_word_only(cats):
    # "P3" must not match inside "P3X"; "ATZ" must not match inside "ATZE".
    result = run("Modell P3X und ATZE", cats)

    assert candidate(result, "BAV07").score == 0
    assert candidate(result, "AZF01").score == 0


def test_fuzzy_match_on_long_keyword_counts_less(cats):
    exact = run("Pflichtverletzung", cats)
    fuzzy = run("Pflichtverletzunq", cats)  # OCR error: g -> q

    exact_score = candidate(exact, "DIS01").score
    fuzzy_score = candidate(fuzzy, "DIS01").score
    assert 0 < fuzzy_score < exact_score
    assert fuzzy_score == pytest.approx(exact_score * 0.7, abs=1e-3)
    assert [m.kind for m in candidate(fuzzy, "DIS01").matched_phrases] == ["fuzzy"]


def test_fuzzy_multi_word_phrase(cats):
    result = run("mit arbeitsrechtlichen Konsequenzen", cats)  # inflected, not exact

    kinds = {m.keyword: m.kind for m in candidate(result, "DIS01").matched_phrases}
    assert kinds.get("arbeitsrechtliche Konsequenzen") in {"prefix", "fuzzy"}


def test_short_keywords_never_fuzzy(cats):
    result = run("P8 Modell", cats)  # one character from "P3"

    assert candidate(result, "BAV07").score == 0


def test_distinct_hits_only(cats):
    once = run("Abmahnung", cats)
    many = run("Abmahnung " * 20, cats)

    assert candidate(once, "DIS01").score == candidate(many, "DIS01").score


def test_cap_limits_score(cats):
    two = run("Pflichtverletzung Personalakte", cats)
    three = run("Pflichtverletzung Personalakte arbeitsrechtliche Konsequenzen", cats)

    assert candidate(three, "DIS01").score > candidate(two, "DIS01").score
    # With cap 2, the third phrase adds nothing.
    capped2 = run("Pflichtverletzung Personalakte", cats, phrase_cap=2)
    capped3 = run("Pflichtverletzung Personalakte arbeitsrechtliche Konsequenzen", cats, phrase_cap=2)
    assert candidate(capped2, "DIS01").score == candidate(capped3, "DIS01").score


def test_shared_keywords_count_less(cats):
    # "Checkliste" is listed by AZF01 and FAM07; "Schutzfrist" only by FAM07.
    shared = run("Checkliste", cats)
    unique = run("Schutzfrist", cats)

    assert candidate(shared, "FAM07").score < candidate(unique, "FAM07").score


def test_negative_phrase_penalises(cats):
    evidence = "Abmahnung abgemahnt Pflichtverletzung Personalakte"
    clean = run(evidence, cats)
    negated = run(evidence + " Ermahnung", cats)

    assert candidate(negated, "DIS01").score == pytest.approx(candidate(clean, "DIS01").score - 0.15, abs=1e-3)
    assert [m.keyword for m in candidate(negated, "DIS01").matched_negatives] == ["Ermahnung"]


def test_score_is_clipped_at_zero(cats):
    result = run("Ermahnung", cats)

    assert candidate(result, "DIS01").score == 0


def test_breakdown_in_cli_json_shape(cats):
    result = run("Abmahnung Pflichtverletzunq", cats)
    data = result.to_dict()

    best = data["candidates"][0]
    assert best["matched_synonyms"] == [
        {"keyword": "Abmahnung", "kind": "exact", "weight": 1.0, "position": "top", "size": 1.0}
    ]
    assert best["matched_phrases"][0]["kind"] == "fuzzy"
    assert "candidates_all" not in data  # full ranking is for the API, not the JSON output


def test_decomposed_umlauts_match_exactly(cats):
    # Some PDFs store "ü" as "u" + a combining diaeresis (Unicode NFD).
    import unicodedata

    result = run(unicodedata.normalize("NFD", "Ärztliche Datenschutzerklärung und Vertraulichkeit"), cats)

    best = candidate(result, "VPF01")
    assert [(m.keyword, m.kind) for m in best.matched_synonyms] == [("Datenschutzerklaerung", "exact")]
