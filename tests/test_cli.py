import json
import subprocess
import sys

from conftest import REAL_CATEGORIES


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "docclassifier", *map(str, args)],
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
