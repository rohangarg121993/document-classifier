"""Feedback loop: labels a person validated in a review file improve later runs (ADR-0004)."""

import json

from conftest import HEADER
from test_cli import run_cli

AMBIGUOUS_PAGE = [(80, "Formular 7"), (140, "Bitte ausfüllen und an die Personalabteilung zurücksenden.")]


def write_review(path, rows):
    path.write_text(
        "file,page,predicted_id,confidence,top3,expected_category_id\n"
        + "".join(f"{file},{page},UNCLASSIFIED,0.0,,{expected}\n" for file, page, expected in rows),
        encoding="utf-8",
    )
    return path


def classify_page(pdf, page, categories):
    proc = run_cli("classify", pdf, "--page", page, "--categories", categories)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_validated_page_gets_its_label_back_even_when_renamed(make_pdf, categories_csv, tmp_path):
    pdf = make_pdf([AMBIGUOUS_PAGE], name="scan_0001.pdf")
    assert classify_page(pdf, 1, categories_csv)["category_id"] == "UNCLASSIFIED"
    review = write_review(tmp_path / "review.csv", [(pdf.name, 1, "GES01")])

    proc = run_cli("learn", review)
    assert proc.returncode == 0, proc.stderr

    renamed = make_pdf([AMBIGUOUS_PAGE], name="Krank_Beispiel.pdf")
    out = classify_page(renamed, 1, categories_csv)
    assert out["category_id"] == "GES01"
    assert out["category_name"] == "Arbeitsunfähigkeit"
    assert out["status"] == "validated"


def form_page(name, date, number):
    return [
        (80, "Formular 7"),
        (140, f"Name: {name}   Personalnummer: {number}"),
        (160, f"Erster Tag: {date}   Voraussichtlich bis: {date}"),
        (180, "Bitte ausfüllen und an die Personalabteilung zurücksenden."),
        (200, "Kopie an die Lohnbuchhaltung, Original zur Akte."),
    ]


def test_new_page_like_a_validated_one_is_classified_the_same(make_pdf, categories_csv, tmp_path):
    validated = make_pdf([form_page("Anna Beispiel", "03.05.2026", "4711")], name="a.pdf")
    review = write_review(tmp_path / "review.csv", [(validated.name, 1, "GES01")])
    new = make_pdf([form_page("Jonas Muster", "17.09.2026", "5820")], name="b.pdf")
    assert classify_page(new, 1, categories_csv)["category_id"] == "UNCLASSIFIED"

    assert run_cli("learn", review).returncode == 0

    out = classify_page(new, 1, categories_csv)
    assert out["category_id"] == "GES01"
    assert out["status"] == "classified"
