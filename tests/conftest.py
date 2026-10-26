from pathlib import Path

import pymupdf
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_CATEGORIES = REPO_ROOT / "config" / "categories.csv"

HEADER = "category_id,category_name,description,synonyms,positive_phrases,negative_phrases,parent_category\n"


@pytest.fixture
def categories_csv(tmp_path):
    """A small synthetic taxonomy, written in the same schema as the real one."""
    path = tmp_path / "categories.csv"
    path.write_text(
        HEADER
        + 'DIS01,Abmahnungen,"Schreiben, das ein Fehlverhalten rügt.",Abmahnung; abgemahnt,Fehlverhalten; Personalakte,Ermahnung,Abmahnung & Disziplinar\n'
        + 'ZEU03,Zwischenzeugnis,"Zeugnis während des laufenden Arbeitsverhältnisses.",Zwischenzeugnis,Tätigkeit; Leistung,verlässt,Zeugnisse & Qualifikation\n'
        + 'GES01,Arbeitsunfähigkeit,"Bescheinigung über Arbeitsunfähigkeit.",Arbeitsunfähigkeitsbescheinigung; Krankmeldung,Diagnose,,Gesundheit & Arbeitsschutz\n',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def make_pdf(tmp_path):
    """Write a synthetic digital PDF. Each page is a list of (y_position, text) lines."""

    def _make(pages, name="doc.pdf"):
        path = tmp_path / name
        doc = pymupdf.open()
        for lines in pages:
            page = doc.new_page(width=595, height=842)  # A4 in points
            for y, text in lines:
                page.insert_text((72, y), text, fontsize=12)
        doc.save(path)
        doc.close()
        return path

    return _make
