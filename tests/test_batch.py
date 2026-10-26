"""Batch classification through the CLI: all pages, folders, parallel workers, per-page errors."""

import json

from conftest import REAL_CATEGORIES
from test_cli import run_cli

WARNING = [
    (80, "Abmahnung"),
    (140, "wegen Ihrer Pflichtverletzung am 3. Mai erteilen wir Ihnen eine Abmahnung."),
    (160, "Im Wiederholungsfall drohen arbeitsrechtliche Konsequenzen. Kopie zur Personalakte."),
]
FILLER = [(80, "Dieses Blatt enthält nur allgemeine Hinweise ohne besonderen Inhalt.")]


def records(proc):
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_all_pages_of_a_file_as_json_lines(make_pdf):
    pdf = make_pdf([FILLER, WARNING, FILLER])

    proc = run_cli("classify", pdf, "--categories", REAL_CATEGORIES)

    assert proc.returncode == 0, proc.stderr
    out = records(proc)
    assert [(r["file"], r["page"]) for r in out] == [(str(pdf), 1), (str(pdf), 2), (str(pdf), 3)]
    assert out[1]["category_id"] == "DIS01"


def test_folder_processes_supported_files_in_sorted_order(make_pdf, tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    a = make_pdf([FILLER, WARNING], name="inbox/a.pdf")
    b = make_pdf([WARNING], name="inbox/b.pdf")
    (folder / "notes.txt").write_text("not a document", encoding="utf-8")

    proc = run_cli("classify", folder, "--categories", REAL_CATEGORIES)

    assert proc.returncode == 0, proc.stderr
    assert [(r["file"], r["page"]) for r in records(proc)] == [(str(a), 1), (str(a), 2), (str(b), 1)]


def test_workers_do_not_change_results(make_pdf, tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    for i in range(3):
        make_pdf([WARNING, FILLER], name=f"inbox/{i}.pdf")

    def stable(proc):
        return [{k: v for k, v in r.items() if k != "timings_ms"} for r in records(proc)]

    one = run_cli("classify", folder, "--categories", REAL_CATEGORIES, "--workers", 1)
    three = run_cli("classify", folder, "--categories", REAL_CATEGORIES, "--workers", 3)

    assert one.returncode == three.returncode == 0, three.stderr
    assert stable(one) == stable(three)
    assert len(stable(one)) == 6


def test_unreadable_file_becomes_an_error_record(make_pdf, tmp_path):
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "a_broken.pdf").write_bytes(b"%PDF-1.7 this is not really a pdf")
    good = make_pdf([WARNING], name="inbox/b_good.pdf")

    proc = run_cli("classify", folder, "--categories", REAL_CATEGORIES)

    out = records(proc)
    assert proc.returncode == 1
    assert out[0]["status"] == "error" and out[0]["file"].endswith("a_broken.pdf") and out[0]["error"]
    assert (out[1]["file"], out[1]["category_id"]) == (str(good), "DIS01")
