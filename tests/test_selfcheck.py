"""`selfcheck` through the CLI: synthetic page per category, rank/margin report, collision pairs, exit code."""

import json

import pytest

from conftest import HEADER
from test_cli import run_cli

ROWS = [
    'DIS01,Abmahnungen,"Schreiben, das ein Fehlverhalten rügt und Konsequenzen androht.",Abmahnung,Pflichtverletzung; Personalakte,,Disziplinar',
    'AZF02,Checkliste LAKO,"Checkliste zum Langzeitkonto.",Langzeitkonto,Checkliste; Wertguthaben,,Arbeitszeit',
    'AZF05,LAKO Freiphase,"Checkliste zum Langzeitkonto.",Langzeitkonto,Checkliste; Wertguthaben,,Arbeitszeit',
]


@pytest.fixture
def colliding_csv(tmp_path):
    path = tmp_path / "cats.csv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return path


def test_reports_colliding_categories_and_fails(colliding_csv):
    proc = run_cli("selfcheck", "--categories", colliding_csv, "--json")

    report = json.loads(proc.stdout)
    assert proc.returncode == 1
    assert report["summary"] == {"categories": 3, "passed": 1, "failed": 2}
    by_id = {c["category_id"]: c for c in report["categories"]}
    assert by_id["DIS01"]["passed"] is True and by_id["DIS01"]["rank"] == 1
    assert by_id["AZF05"]["passed"] is False
    assert by_id["AZF05"]["runner_up"] == "AZF02"
    assert ["AZF02", "AZF05"] in report["collisions"]


def test_max_failures_threshold(colliding_csv):
    assert run_cli("selfcheck", "--categories", colliding_csv, "--max-failures", 2).returncode == 0
    assert run_cli("selfcheck", "--categories", colliding_csv, "--max-failures", 1).returncode == 1
