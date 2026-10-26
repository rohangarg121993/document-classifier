"""Page regions, exercised through `classify` with PageText fixtures that carry word positions."""

from dataclasses import replace

import pytest

from docclassifier import classify, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import HEADER

HEIGHT = 842.0
FILLER = "lorem ipsum dolor sit amet consectetur"
TOP, MIDDLE, BOTTOM = 60.0, 420.0, 780.0

ROWS = [
    "DIS01,Abmahnungen,x,Abmahnung,,,Disziplinar",
    "FIN01,Kontoauszug,x,Kontoauszug,,,Finanzen",
    "FIN09,Kontoauszug unten,x,Kontoauszug,,,Finanzen",
]


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    header = HEADER.rstrip("\n") + ",weight_bottom\n"
    rows = [ROWS[0] + ",", ROWS[1] + ",", ROWS[2] + ",0.9"]
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return load_categories(path)


def page(lines):
    """`lines` is a list of (y, text). Words get boxes on that line."""
    words, texts = [], []
    for y, text in lines:
        x = 72.0
        for token in text.split():
            words.append(Word(token, x, y - 6, x + 8 * len(token), y + 6))
            x += 8 * len(token) + 4
        texts.append(text)
    return PageText("\n".join(texts), words, 595.0, HEIGHT, "native", 1)


def run(p, cats, **classifier_overrides):
    settings = load_settings()
    classifier = replace(settings.classifier, similarity_weight=0, **classifier_overrides)
    return classify(p, cats, replace(settings, classifier=classifier))


def score(result, category_id):
    return next(c for c in result.candidates_all if c.category_id == category_id).score


def test_keyword_at_top_counts_more_than_at_bottom(cats):
    at_top = page([(TOP, "Abmahnung " + FILLER), (MIDDLE, FILLER), (BOTTOM, FILLER)])
    at_bottom = page([(TOP, FILLER), (MIDDLE, FILLER), (BOTTOM, "Abmahnung " + FILLER)])

    assert score(run(at_top, cats), "DIS01") > score(run(at_bottom, cats), "DIS01")


def test_empty_regions_share_their_weight(cats):
    # Text only at the top: top (0.40) and full (0.25) are active and renormalised to 1.
    # Both see one of DIS01's synonyms: 0.35 · 1/3 ≈ 0.1167, which is the whole score; no loss from empty regions.
    only_top = page([(TOP, "Abmahnung " + FILLER)])

    result = run(only_top, cats)

    best = next(c for c in result.candidates_all if c.category_id == "DIS01")
    assert best.score == pytest.approx(0.1167, abs=1e-3)
    assert set(best.regions) == {"top", "full"}
    assert best.regions["top"].weight == pytest.approx(0.40 / 0.65, abs=1e-3)


def test_per_category_region_weight_override(cats):
    # FIN09 overrides weight_bottom = 0.9; FIN01 uses the global 0.15. Same keyword, at the bottom.
    p = page([(TOP, FILLER), (MIDDLE, FILLER), (BOTTOM, "Kontoauszug " + FILLER)])

    result = run(p, cats)

    assert score(result, "FIN09") > score(result, "FIN01")


def test_line_split_fallback_without_word_positions(cats):
    lines = ["Abmahnung " + FILLER] + [FILLER] * 8
    at_top = PageText("\n".join(lines), [], 595.0, HEIGHT, "native", 1)
    at_bottom = PageText("\n".join(reversed(lines)), [], 595.0, HEIGHT, "native", 1)

    assert score(run(at_top, cats), "DIS01") > score(run(at_bottom, cats), "DIS01")


def test_breakdown_per_region_in_json(cats):
    p = page([(TOP, "Abmahnung " + FILLER), (MIDDLE, FILLER), (BOTTOM, FILLER)])

    data = run(p, cats).to_dict()

    regions = next(c for c in data["candidates"] if c["category_id"] == "DIS01")["regions"]
    assert set(regions) == {"top", "middle", "bottom", "full"}
    assert [m["keyword"] for m in regions["top"]["matched_synonyms"]] == ["Abmahnung"]
    assert regions["bottom"]["matched_synonyms"] == []
    assert "similarity" in regions["top"]
