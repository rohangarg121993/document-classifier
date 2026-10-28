"""Title-first classification (ADR-0005), exercised through `classify` with positioned synthetic pages.

A page is judged the way a person reads it: find the document's title (subject line, prominent heading, form
header), match that against the categories, and use the body only when the title doesn't decide.
"""

from dataclasses import replace

import pytest

from docclassifier import classify, load_categories, load_settings
from docclassifier.ocr import PageText, Word

from conftest import HEADER

ROWS = [
    "DIS01,Abmahnungen,Schreiben das ein Fehlverhalten rügt,Abmahnung,Pflichtverletzung; Personalakte,Ermahnung,Disziplinar",
    "DIS03,Ermahnungen,Hinweis an Mitarbeiter zur Einhaltung von Pflichten als Vorstufe zur Verwarnung,Ermahnung,ermahnen; Hinweis; künftig,Abmahnung,Disziplinar",
    "AUS05,Kündigung,Kündigung des Arbeitsverhältnisses durch den Arbeitgeber,Kündigung,kündigen wir; fristgerecht,,Austritt",
    "AUS04,MA Kuendigung,Kündigungsschreiben das vom Mitarbeiter ausgeht,Kündigung; Eigenkündigung,hiermit kündige ich; mein Arbeitsverhältnis,kündigen wir,Austritt",
    "VTR01,Befristeter Arbeitsvertrag,Arbeitsvertrag mit Befristung und Enddatum,befristeter Arbeitsvertrag,befristet; endet am; Sachgrund,unbestimmte Zeit,Vertrag",
    "VTR02,Unbefristeter Arbeitsvertrag,Arbeitsvertrag ohne Enddatum,Arbeitsvertrag,unbestimmte Zeit; Probezeit,befristet,Vertrag",
    "ZEU01,Arbeitszeugnisse extern,Zeugnis eines früheren Arbeitgebers,Arbeitszeugnis; Zeugnis,vollsten Zufriedenheit,Zwischenzeugnis,Zeugnisse",
    "AUS01,Aufhebungsvertraege,Zweiseitige Vereinbarung über die einvernehmliche Beendigung des Arbeitsverhältnisses mit Abfindung,Aufhebungsvertrag,einvernehmlich; Abfindung; Ausgleichsklausel,,Austritt",
    "ZUS07,Rechnungen Unterkunft,Rechnungen für Hotel und Umzug,Rechnung; Hotelrechnung,Rechnungsnummer; Übernachtung,,Zusatzleistungen",
    "ZEU03,Zwischenzeugnis,Zeugnis während des laufenden Arbeitsverhältnisses,Zwischenzeugnis,ist seit; stets,verlässt,Zeugnisse",
]


@pytest.fixture
def cats(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return load_categories(path)


def page(lines):
    """`lines`: (y, text, font_size) or (y, text, font_size, x) on an A4 page, y measured from the top."""
    words, texts = [], []
    for y, text, size, *rest in lines:
        x = rest[0] if rest else 70.0
        for token in text.split():
            width = 0.5 * size * len(token)
            words.append(Word(token, x, y - size, x + width, y))
            x += width + 0.3 * size
        texts.append(text)
    return PageText("\n".join(texts), words, 595.0, 842.0, "native", 1)


def run(p, cats):
    return classify(p, cats, load_settings())


def letter(subject, body):
    """A DIN 5008 business letter: letterhead, address block, subject line, body, footer."""
    return page(
        [(52, "Nordwerk Anlagenbau GmbH", 16, 360), (68, "Hafenstraße 12 · 28217 Bremen", 8, 360),
         (140, "Nordwerk Anlagenbau GmbH · Hafenstraße 12 · 28217 Bremen", 7),
         (162, "Herrn", 10), (175, "Jonas Muster", 10), (188, "Lindenweg 4", 10), (201, "28195 Bremen", 10),
         (230, "Bremen, 14.03.2026", 10, 360),
         (290, subject, 10)]
        + [(330 + 13.5 * i, line, 10) for i, line in enumerate(body)]
        + [(792, "Amtsgericht Bremen HRB 99117 · IBAN DE12 2905 0101 0001 2345 67", 7)]
    )


def test_subject_line_decides_over_document_types_mentioned_in_the_body(cats):
    p = letter(
        "Betreff: Abmahnung wegen unentschuldigten Fehlens",
        ["Sehr geehrter Herr Muster,",
         "am 10.03.2026 sind Sie unentschuldigt nicht zur Arbeit erschienen.",
         "Damit haben Sie gegen Ihre Pflichten aus dem Arbeitsvertrag verstoßen.",
         "Im Wiederholungsfall müssen Sie mit einer Kündigung rechnen."],
    )

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "DIS01")
    assert result.title == "Abmahnung wegen unentschuldigten Fehlens"


def test_subject_line_without_prefix_is_the_line_before_the_salutation(cats):
    # DIN 5008 dropped "Betreff:"; the subject is the line that leads into the salutation.
    p = letter(
        "Kündigung Ihres Arbeitsverhältnisses",
        ["Sehr geehrter Herr Muster,",
         "hiermit kündigen wir das mit Ihnen bestehende Arbeitsverhältnis fristgerecht zum 30.06.2026.",
         "Die Abmahnung vom 02.02.2026 liegt Ihnen vor."],
    )

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "AUS05")
    assert result.title == "Kündigung Ihres Arbeitsverhältnisses"


def test_large_print_heading_is_the_title_of_a_page_without_salutation(cats):
    p = page(
        [(80, "Arbeitsvertrag", 18, 230),
         (120, "zwischen der Nordwerk Anlagenbau GmbH, Hafenstraße 12, 28217 Bremen", 10),
         (134, "und Herrn Jonas Muster, Lindenweg 4, 28195 Bremen", 10),
         (170, "§ 1 Beginn und Dauer", 11),
         (184, "Das Arbeitsverhältnis beginnt am 01.04.2026 und wird auf unbestimmte Zeit geschlossen.", 10),
         (210, "§ 2 Kündigung", 11),
         (224, "Eine Kündigung ist mit den gesetzlichen Fristen möglich; vor einer Kündigung erfolgt eine Abmahnung.", 10)]
    )

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "VTR02")
    assert result.title == "Arbeitsvertrag"


def test_title_compound_counts_by_its_last_part(cats):
    # "Verhaltensabmahnung" is an Abmahnung; the first part only says what kind.
    p = letter("Verhaltensabmahnung", ["Sehr geehrter Herr Muster,", "wir mahnen Sie hiermit ab."])

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "DIS01")


def test_most_specific_document_name_in_the_title_wins(cats):
    # "Zeugnis" is the last part of "Zwischenzeugnis", but the longer name says exactly which kind.
    p = page([(80, "Zwischenzeugnis", 18, 230), (130, "Herr Jonas Muster ist seit dem 01.04.2019 bei uns beschäftigt.", 10)])

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "ZEU03")


@pytest.mark.encoder
def test_title_worded_unlike_any_synonym_is_matched_by_meaning(cats):
    # No synonym ("Aufhebungsvertrag") appears; the page says the same thing in other words.
    p = letter(
        "Ihr Ausscheiden aus unserem Unternehmen",
        ["Sehr geehrter Herr Muster,",
         "wie besprochen endet Ihr Arbeitsverhältnis im gegenseitigen Einvernehmen zum 30.06.2026.",
         "Als Ausgleich für den Verlust des Arbeitsplatzes erhalten Sie eine Zahlung von 18.000 EUR brutto.",
         "Mit der Erfüllung dieser Vereinbarung sind alle gegenseitigen Ansprüche erledigt."],
    )

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "AUS01")


def test_form_label_starting_with_betr_is_not_a_subject_line(cats):
    # "Betriebsstätten-Nr." starts like the abbreviation "Betr.", but it is a form field.
    p = page([(80, "Abmahnung", 18, 230), (130, "Betriebsstätten-Nr. 4711 Arzt-Nr. 0815", 10),
              (150, "Sie haben wiederholt gegen die Arbeitszeitregelung verstoßen.", 10)])

    result = run(p, cats)

    assert result.title == "Abmahnung"


def test_letterhead_in_larger_print_than_the_title_is_not_the_title(cats):
    p = page([(50, "Kaiser & Lindholm Logistik AG", 18, 330), (64, "Am Speicher 3 · 20457 Hamburg", 8, 330),
              (200, "Abmahnung", 14, 70),
              (240, "Sie haben am 03.02.2026 ohne Genehmigung das Lager verlassen.", 10),
              (254, "Wir fordern Sie auf, dieses Verhalten künftig zu unterlassen.", 10)])

    result = run(p, cats)

    assert (result.category_id, result.title) == ("DIS01", "Abmahnung")


def test_word_with_a_short_prefix_is_not_a_compound_of_the_synonym(cats):
    # "Abrechnung" is a settlement, not a Rechnung: "Ab-" is a prefix, not a word of its own.
    p = page([(80, "Abrechnung Dienstreise", 18, 200), (130, "Fahrtkosten Bahn 89,00 EUR", 10)])

    result = run(p, cats)

    assert all(m.keyword != "Rechnung" for c in result.candidates_all for m in c.matched_synonyms)


def test_compound_of_two_words_still_counts_by_its_last_part(cats):
    # "Taxirechnung" is not listed, but "Taxi" is a word of its own: a Rechnung for a taxi ride.
    p = page([(80, "Taxirechnung", 18, 200), (130, "Fahrt vom Bahnhof zum Hotel am 03.03.2026", 10)])

    assert run(p, cats).category_id == "ZUS07"


def test_title_naming_two_siblings_is_decided_by_the_body(cats):
    # "Kündigung" names both AUS04 (by the employee) and AUS05 (by the employer); the body says who gives notice.
    p = page([(60, "Jonas Muster · Lindenweg 4 · 28195 Bremen", 9), (200, "Kündigung", 14),
              (240, "Sehr geehrte Damen und Herren,", 10),
              (254, "hiermit kündige ich mein Arbeitsverhältnis fristgerecht zum 30.06.2026.", 10)])

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "AUS04")


def test_title_naming_the_general_type_lets_its_specific_sibling_compete(cats):
    # The title only says "Arbeitsvertrag"; the body shows which kind: a fixed-term one.
    p = page([(80, "Arbeitsvertrag", 18, 230),
              (130, "Das Arbeitsverhältnis ist befristet und endet am 31.12.2026, ohne dass es einer Kündigung bedarf.", 10),
              (144, "Die Befristung erfolgt ohne Sachgrund nach § 14 Abs. 2 TzBfG.", 10)])

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "VTR01")


def test_page_with_too_little_text_is_not_classified(cats):
    # A stray word or two of OCR noise is no document, even if it happens to read like a title.
    result = run(page([(80, "Abmahnung", 18, 230)]), cats)

    assert (result.status, result.reason) == ("unclassified", "insufficient_text")


def test_every_category_is_ranked_with_the_title_match_first(cats):
    p = letter("Betreff: Abmahnung", ["Sehr geehrter Herr Muster,", "Sie haben wiederholt gegen Ihre Pflichten verstoßen."])

    ranked = [c.category_id for c in run(p, cats).candidates_all]

    assert ranked[0] == "DIS01"
    assert sorted(ranked) == sorted(row.split(",")[0] for row in ROWS)


def test_suspected_handwriting_sends_a_title_match_to_review(cats):
    # OCR of handwriting is unreliable: the title may be misread, so a person checks it.
    p = letter("Betreff: Abmahnung", ["Sehr geehrter Herr Muster,", "Sie haben wiederholt gegen Ihre Pflichten verstoßen."])

    result = run(replace(p, handwriting_suspected=True), cats)

    assert result.status != "classified"
    assert result.confidence <= load_settings().decision.handwriting_confidence_cap
    assert result.candidates[0].category_id == "DIS01"


def test_page_without_a_category_goes_to_the_fallback_category_when_one_is_set(cats):
    settings = load_settings()
    settings = replace(
        settings, decision=replace(settings.decision, fallback_category_id="ZUS07"),
    )

    result = classify(page([(80, "Seite 2", 10)]), cats, settings)

    assert (result.status, result.category_id) == ("fallback", "ZUS07")


@pytest.mark.encoder
def test_siblings_too_close_to_call_still_give_their_parent(cats):
    # "Kündigung", and the body doesn't say who gives notice: certainly an Austritt, unsure which one.
    p = page([(80, "Kündigung", 18, 230), (130, "Ihr Arbeitsverhältnis endet mit Ablauf des 30.06.2026.", 10)])

    result = run(p, cats)

    assert (result.status, result.category_id, result.parent_category) == ("parent_only", "UNCLASSIFIED", "Austritt")


def test_short_first_line_in_body_print_is_the_title(cats):
    # Many PDFs set the title in bold at the text size: no large print, no subject line, no salutation.
    p = page([(60, "Zwischenzeugnis", 10),
              (100, "Frau Beispiel ist seit dem 1. April 2019 in unserem Unternehmen als Sachbearbeiterin tätig.", 10),
              (114, "Ihre Leistung war stets einwandfrei; die Kündigungsfrist beträgt sechs Wochen.", 10)])

    result = run(p, cats)

    assert (result.status, result.category_id, result.title) == ("classified", "ZEU03", "Zwischenzeugnis")


@pytest.mark.encoder
def test_title_naming_one_category_wins_over_its_siblings_unless_the_body_clearly_differs(cats):
    # The body reads like any disciplinary letter; nothing in it contradicts the title "Abmahnung".
    p = letter("Betreff: Abmahnung", ["Sehr geehrter Herr Muster,",
                                     "wir weisen Sie darauf hin, dass Sie die Arbeitszeiten künftig einzuhalten haben."])

    result = run(p, cats)

    assert (result.status, result.category_id) == ("classified", "DIS01")


def test_form_field_with_an_amount_is_not_a_title(cats):
    # A short table row near the top of a form names a cost type, not the document.
    p = page([(60, "Dienstreise Hamburg – Kostenaufstellung", 10),
              (90, "Rechnung Hotel 240,00", 10),
              (104, "Bahnfahrt 2. Klasse 89,00", 10),
              (300, "Bitte erstatten Sie den Gesamtbetrag auf mein Gehaltskonto; die Belege liegen bei.", 10)])

    result = run(p, cats)

    assert all(m.keyword != "Rechnung" for c in result.candidates_all for m in c.matched_synonyms)
