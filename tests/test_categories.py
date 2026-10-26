import math

import pytest

from docclassifier import load_categories
from docclassifier.classify import CategoryFileError

from conftest import HEADER, REAL_CATEGORIES

ROWS = [
    "DIS01,Abmahnungen,Rügt Fehlverhalten.,Abmahnung,Fehlverhalten; Checkliste,Ermahnung,Disziplinar",
    "AZF01,ATZ Checkliste,Prüfliste Altersteilzeit.,ATZ,Checkliste; Altersteilzeit,,Arbeitszeit",
]


def write(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "cats.csv"
    path.write_bytes(text.encode(encoding))
    return path


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252"])
@pytest.mark.parametrize("delimiter", [",", ";"])
def test_detects_encoding_and_delimiter(tmp_path, encoding, delimiter):
    header = HEADER.replace(",", delimiter)
    # With ';' as the column delimiter, list cells must be quoted so their ';' isn't read as a column break.
    rows = [
        delimiter.join(f'"{cell}"' for cell in row.split(",")) if delimiter == ";" else row
        for row in ROWS
    ]
    path = write(tmp_path, header + "\n".join(rows) + "\n", encoding)

    categories = load_categories(path)

    assert [c.category_id for c in categories] == ["DIS01", "AZF01"]
    assert categories[0].description == "Rügt Fehlverhalten."
    assert categories[0].positive_phrases == ["Fehlverhalten", "Checkliste"]
    assert categories[1].negative_phrases == []


def test_duplicate_ids_are_fatal(tmp_path):
    path = write(tmp_path, HEADER + ROWS[0] + "\n" + ROWS[0] + "\n")

    with pytest.raises(CategoryFileError, match=r"Duplicate category_id 'DIS01'.*rows 2 and 3"):
        load_categories(path)


def test_missing_required_column_is_fatal(tmp_path):
    header = HEADER.replace(",negative_phrases", "")
    row = ROWS[0].replace(",Ermahnung", "")
    path = write(tmp_path, header + row + "\n")

    with pytest.raises(CategoryFileError, match="Missing required column.*negative_phrases"):
        load_categories(path)


def test_keyword_both_positive_and_negative_is_fatal(tmp_path):
    row = "DIS01,Abmahnungen,x,Abmahnung,Fehlverhalten,fehlverhalten,Disziplinar"
    path = write(tmp_path, HEADER + row + "\n")

    with pytest.raises(CategoryFileError, match=r"DIS01.*both positive and negative.*fehlverhalten"):
        load_categories(path)


def test_all_problems_reported_together(tmp_path):
    bad_conflict = "ZZZ01,X,x,Foo,,foo,P"
    path = write(tmp_path, HEADER + ROWS[0] + "\n" + ROWS[0] + "\n" + bad_conflict + "\n")

    with pytest.raises(CategoryFileError) as err:
        load_categories(path)

    assert "Duplicate" in str(err.value) and "ZZZ01" in str(err.value)


def test_synonym_shared_across_categories_warns(tmp_path):
    rows = [
        "ZEU01,Zeugnis extern,x,Arbeitszeugnis; Endzeugnis,,,Zeugnisse",
        "ZEU05,Abschlusszeugnis,x,Abschlusszeugnis; Endzeugnis,,,Zeugnisse",
    ]
    path = write(tmp_path, HEADER + "\n".join(rows) + "\n")

    categories = load_categories(path)

    assert len(categories) == 2
    assert any("endzeugnis" in w and "ZEU01" in w and "ZEU05" in w for w in categories.warnings)


def test_specificity_weight_shrinks_with_sharing(tmp_path):
    path = write(tmp_path, HEADER + "\n".join(ROWS) + "\n")

    categories = load_categories(path)

    assert categories.specificity("Abmahnung") == 1.0  # one category
    assert categories.specificity("checkliste") == pytest.approx(1 / (1 + math.log(2)))
    assert categories.specificity("not a keyword") == 1.0


def test_optional_region_weight_columns(tmp_path):
    header = HEADER.rstrip("\n") + ",weight_top,weight_bottom\n"
    rows = [ROWS[0] + ",0.6,0.1", ROWS[1] + ",,"]
    path = write(tmp_path, header + "\n".join(rows) + "\n")

    categories = load_categories(path)

    assert categories[0].region_weights == {"top": 0.6, "bottom": 0.1}
    assert categories[1].region_weights == {}  # empty cells: global weights apply


def test_invalid_region_weight_is_fatal(tmp_path):
    header = HEADER.rstrip("\n") + ",weight_top\n"
    path = write(tmp_path, header + ROWS[0] + ",high\n")

    with pytest.raises(CategoryFileError, match="weight_top.*high"):
        load_categories(path)


def test_real_taxonomy_loads_without_errors():
    categories = load_categories(REAL_CATEGORIES)

    assert len(categories) == 144
    assert categories.warnings  # known shared synonyms such as "Endzeugnis"
