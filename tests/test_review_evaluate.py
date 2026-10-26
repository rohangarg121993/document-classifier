"""Review file and `evaluate`, through the CLI: build labels from normal use, then measure accuracy."""

import csv
import json

import pytest

from conftest import REAL_CATEGORIES
from test_batch import FILLER, WARNING
from test_cli import run_cli

REFERENCE = [
    (80, "Zwischenzeugnis"),
    (140, "Frau Beispiel ist seit 2019 in unserem Unternehmen tätig."),
    (160, "Ihre Leistung und ihre Tätigkeit beurteilen wir sehr positiv."),
]


@pytest.fixture
def inbox(make_pdf, tmp_path):
    (tmp_path / "inbox").mkdir()
    make_pdf([WARNING, FILLER], name="inbox/a.pdf")
    make_pdf([REFERENCE], name="inbox/b.pdf")
    return tmp_path / "inbox"


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_review_file_prefills_expected_with_prediction(inbox, tmp_path):
    review = tmp_path / "review.csv"

    proc = run_cli("classify", inbox, "--categories", REAL_CATEGORIES, "--review-out", review)

    assert proc.returncode == 0, proc.stderr
    rows = read_csv(review)
    assert list(rows[0]) == ["file", "page", "predicted_id", "confidence", "top3", "expected_category_id"]
    assert [(r["file"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1], r["page"]) for r in rows] == [
        ("a.pdf", "1"), ("a.pdf", "2"), ("b.pdf", "1"),
    ]
    assert rows[0]["predicted_id"] == "DIS01"
    assert all(r["expected_category_id"] == r["predicted_id"] for r in rows)
    assert rows[0]["top3"].startswith("DIS01:")


def correct(review, page_file, page, label):
    rows = read_csv(review)
    for r in rows:
        if r["file"].endswith(page_file) and r["page"] == str(page):
            r["expected_category_id"] = label
    with open(review, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def test_evaluate_corrected_review_file(inbox, tmp_path):
    review = tmp_path / "review.csv"
    run_cli("classify", inbox, "--categories", REAL_CATEGORIES, "--review-out", review)
    rows = correct(review, "a.pdf", 2, "SON02")  # the reviewer says page 2 is "sonstiges"
    predicted_p2 = next(r["predicted_id"] for r in rows if r["file"].endswith("a.pdf") and r["page"] == "2")

    proc = run_cli("evaluate", review, "--categories", REAL_CATEGORIES, "--json")

    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["summary"] == {"pages": 3, "correct": 2, "accuracy": pytest.approx(2 / 3, abs=1e-3)}
    [miss] = report["misclassified"]
    assert miss["file"].endswith("a.pdf") and miss["page"] == 2
    assert (miss["expected"], miss["predicted"]) == ("SON02", predicted_p2)
    assert len(miss["top3"]) == 3
    assert report["confusion"]["SON02"] == {predicted_p2: 1}
    assert report["confusion"]["DIS01"] == {"DIS01": 1}


def test_evaluate_plain_label_file_and_text_report(inbox, tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "file,page,expected_category_id\n"
        f"{inbox / 'a.pdf'},1,DIS01\n"
        f"{inbox / 'b.pdf'},1,\n",  # blank label: not reviewed yet, skipped
        encoding="utf-8",
    )

    proc = run_cli("evaluate", labels, "--categories", REAL_CATEGORIES)

    assert proc.returncode == 0, proc.stderr
    assert "accuracy 100.0% (1/1 pages)" in proc.stdout
