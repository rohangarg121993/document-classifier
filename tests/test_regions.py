"""Where on the page a hit appears, exercised through `classify` with PageText fixtures carrying word positions.

Synonyms are document-type names, so they count fully only as a title (top third); phrases count a little
less further down. With similarity off, one synonym hit gives strength 0.95 × position factor.
"""

from dataclasses import replace

import pytest

from docclassifier import classify, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import HEADER

HEIGHT = 842.0
FILLER = "lorem ipsum dolor sit amet consectetur"
TOP, MIDDLE, BOTTOM = 60.0, 420.0, 780.0

ROWS = [
    "DIS01,Abmahnungen,x,Abmahnung,Personalakte,,Disziplinar",
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
    classifier = replace(settings.classifier, similarity_reliability=0, **classifier_overrides)
    return classify(p, cats, replace(settings, classifier=classifier))


def score(result, category_id):
    return next(c for c in result.candidates_all if c.category_id == category_id).score


def at(y, text):
    lines = {TOP: FILLER, MIDDLE: FILLER, BOTTOM: FILLER}
    lines[y] = f"{text} {FILLER}"
    return page(sorted(lines.items()))


def test_synonym_counts_fully_only_as_a_title(cats):
    assert score(run(at(TOP, "Abmahnung"), cats), "DIS01") == pytest.approx(0.95, abs=1e-3)
    assert score(run(at(MIDDLE, "Abmahnung"), cats), "DIS01") == pytest.approx(0.95 * 0.30, abs=1e-3)
    assert score(run(at(BOTTOM, "Abmahnung"), cats), "DIS01") == pytest.approx(0.95 * 0.20, abs=1e-3)


def test_phrase_position_matters_less(cats):
    # One phrase: 0.6 · (factor / 3)
    assert score(run(at(TOP, "Personalakte"), cats), "DIS01") == pytest.approx(0.2, abs=1e-3)
    assert score(run(at(BOTTOM, "Personalakte"), cats), "DIS01") == pytest.approx(0.2 * 0.7, abs=1e-3)


def test_per_category_position_override(cats):
    # FIN09 sets weight_bottom = 0.9; FIN01 uses the default bottom factor for synonyms (0.20).
    result = run(at(BOTTOM, "Kontoauszug"), cats)

    assert score(result, "FIN09") == pytest.approx(0.95 * 0.9, abs=1e-3)
    assert score(result, "FIN01") == pytest.approx(0.95 * 0.20, abs=1e-3)


def test_line_split_fallback_without_word_positions(cats):
    lines = ["Abmahnung " + FILLER] + [FILLER] * 8
    at_top = PageText("\n".join(lines), [], 595.0, HEIGHT, "native", 1)
    at_bottom = PageText("\n".join(reversed(lines)), [], 595.0, HEIGHT, "native", 1)

    assert score(run(at_top, cats), "DIS01") > score(run(at_bottom, cats), "DIS01")


def test_short_title_alone_in_top_third_counts(cats):
    # A one-word title is enough: there is no minimum amount of text per region any more.
    p = page([(TOP, "Abmahnung"), (MIDDLE, FILLER), (BOTTOM, FILLER)])

    assert score(run(p, cats), "DIS01") == pytest.approx(0.95, abs=1e-3)


def test_match_positions_in_json(cats):
    data = run(page([(TOP, "Abmahnung"), (MIDDLE, "Personalakte " + FILLER)]), cats).to_dict()

    best = next(c for c in data["candidates"] if c["category_id"] == "DIS01")
    assert [(m["keyword"], m["position"]) for m in best["matched_synonyms"]] == [("Abmahnung", "top")]
    assert [(m["keyword"], m["position"]) for m in best["matched_phrases"]] == [("Personalakte", "middle")]
