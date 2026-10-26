import json
import subprocess
import sys

import pytest

from conftest import REAL_CATEGORIES, REPO_ROOT


def run_cli(*args):
    # The launcher, not `-m docclassifier`, so the CLI runs without the package being installed.
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "docclassify.py"), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_classify_digital_pdf_page_against_real_taxonomy(make_pdf):
    pdf = make_pdf([
        [(80, "Deckblatt")],
        [
            (80, "Abmahnung"),
            (140, "Sehr geehrter Herr Beispiel,"),
            (160, "wegen Ihrer Pflichtverletzung am 3. Mai erteilen wir Ihnen eine Abmahnung."),
            (180, "Im Wiederholungsfall drohen arbeitsrechtliche Konsequenzen."),
            (200, "Eine Kopie geht zur Personalakte."),
        ],
    ])

    proc = run_cli("classify", pdf, "--page", 2, "--categories", REAL_CATEGORIES)

    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["category_id"] == "DIS01"
    assert out["status"] == "classified"
    assert out["page"] == 2
    assert out["extraction_method"] == "native"
    assert set(out["timings_ms"]) == {"extract", "classify"}
    assert "text" not in out


def test_include_text_flag(make_pdf, categories_csv):
    pdf = make_pdf([[(80, "Abmahnung")]])

    proc = run_cli("classify", pdf, "--page", 1, "--categories", categories_csv, "--include-text")

    assert proc.returncode == 0, proc.stderr
    assert "Abmahnung" in json.loads(proc.stdout)["text"]


def test_bad_page_number_exits_nonzero_with_message(make_pdf, categories_csv):
    pdf = make_pdf([[(80, "Abmahnung")]])

    proc = run_cli("classify", pdf, "--page", 9, "--categories", categories_csv)

    assert proc.returncode != 0
    assert "page 9" in proc.stderr


def test_broken_category_file_exits_nonzero_with_all_problems(make_pdf, tmp_path):
    pdf = make_pdf([[(80, "Abmahnung")]])
    bad = tmp_path / "bad.csv"
    bad.write_text("category_id,category_name\nX,Y\n", encoding="utf-8")

    proc = run_cli("classify", pdf, "--page", 1, "--categories", bad)

    assert proc.returncode != 0
    assert "Missing required column" in proc.stderr


@pytest.mark.tesseract
def test_no_cache_flag_leaves_no_cache_behind(make_scan, categories_csv, tmp_path):
    scan = make_scan([[(80, "Abmahnung"), (140, "wegen Ihrer Pflichtverletzung am 3. Mai.")]])

    proc = run_cli("classify", scan, "--page", 1, "--categories", categories_csv, "--no-cache")

    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["extraction_method"] == "ocr"
    assert out["ocr_quality"] == "ok"
    assert out["handwriting_suspected"] is False
    assert not (tmp_path / ".cache").exists()


def test_classify_does_not_print_taxonomy_warnings(make_pdf):
    pdf = make_pdf([[(80, "Abmahnung wegen Pflichtverletzung am 3. Mai")]])

    proc = run_cli("classify", pdf, "--page", 1, "--categories", REAL_CATEGORIES)

    assert proc.returncode == 0
    assert "shared" not in proc.stderr  # taxonomy hygiene belongs to selfcheck, not every classification


def test_selfcheck_reports_shared_synonyms():
    proc = run_cli("selfcheck", "--categories", REAL_CATEGORIES)

    assert "28 synonym(s) are shared" in proc.stdout
    assert "endzeugnis" in proc.stdout
