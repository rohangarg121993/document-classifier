"""Where on the page a hit appears, exercised through `classify` with PageText fixtures carrying word positions.

Synonyms are document-type names, so they count fully as a title (top third or large print) and less in
running text; phrases count a little less further down. With similarity off, one synonym hit gives strength 0.95 × position factor.
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


def test_synonym_as_title_counts_fully(cats):
    assert score(run(at(TOP, "Abmahnung"), cats), "DIS01") == pytest.approx(0.95, abs=1e-3)


def test_phrase_position_matters_less(cats):
    # One phrase: 0.6 · (factor / 3)
    assert score(run(at(TOP, "Personalakte"), cats), "DIS01") == pytest.approx(0.2, abs=1e-3)
    assert score(run(at(BOTTOM, "Personalakte"), cats), "DIS01") == pytest.approx(0.2 * 0.7, abs=1e-3)


def test_per_category_position_override(cats):
    # "Abmahnung" is the title. FIN09 sets weight_bottom = 0.9; FIN01 uses the default bottom factor (0.4).
    result = run(page([(TOP, "Abmahnung " + FILLER), (MIDDLE, FILLER), (BOTTOM, "Kontoauszug " + FILLER)]), cats)

    assert score(result, "FIN09") == pytest.approx(0.95 * 0.9, abs=1e-3)
    assert score(result, "FIN01") == pytest.approx(0.95 * 0.4, abs=1e-3)


def test_line_split_fallback_without_word_positions(cats):
    lines = ["Personalakte " + FILLER] + [FILLER] * 8
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


def big(y, text, height=28.0):
    """A line printed in a large font: taller word boxes than the 12-point body text."""
    words, x = [], 72.0
    for token in text.split():
        words.append(Word(token, x, y - height / 2, x + 14 * len(token), y + height / 2))
        x += 14 * len(token) + 6
    return words


def test_synonym_in_large_print_counts_as_a_title_anywhere(cats):
    body = page([(TOP, FILLER), (TOP + 20, FILLER), (MIDDLE, FILLER), (MIDDLE + 20, FILLER), (BOTTOM - 40, FILLER)])
    label = big(BOTTOM, "Abmahnung")
    p = PageText(body.text + "\nAbmahnung", body.words + label, body.width, body.height, "native", 1)

    result = run(p, cats)

    assert score(result, "DIS01") == pytest.approx(0.95, abs=1e-3)
    match = next(c for c in result.candidates_all if c.category_id == "DIS01").matched_synonyms[0]
    assert match.position == "heading"
    assert match.size >= 2.0  # relative to the page's median word height


def test_without_a_title_the_best_placed_synonym_counts_fully(cats):
    # No document-type name at the top: the lower-placed synonym is the page's de facto title.
    assert score(run(at(BOTTOM, "Kontoauszug"), cats), "FIN01") == pytest.approx(0.95, abs=1e-3)


def test_synonym_in_running_text_counts_less_when_another_type_is_the_title(cats):
    # "Kontoauszug" is the title; "Abmahnung" is merely mentioned further down.
    p = page([(TOP, "Kontoauszug " + FILLER), (MIDDLE, FILLER), (BOTTOM, "Abmahnung " + FILLER)])

    result = run(p, cats)

    assert score(result, "FIN01") == pytest.approx(0.95, abs=1e-3)
    assert score(result, "DIS01") == pytest.approx(0.95 * 0.4, abs=1e-3)
