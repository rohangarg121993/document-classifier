import pytest

from docclassifier import load_settings


def test_defaults_ship_with_package():
    settings = load_settings()

    assert settings.classifier.phrase_cap == 3
    assert settings.ocr.languages == "deu+eng"


def test_user_file_overrides_only_given_keys(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text("[classifier]\nphrase_cap = 5\n", encoding="utf-8")

    settings = load_settings(path)

    assert settings.classifier.phrase_cap == 5
    assert settings.ocr.languages == "deu+eng"


def test_unknown_key_is_rejected(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text("[classifier]\nphrase_capp = 5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="phrase_capp"):
        load_settings(path)
