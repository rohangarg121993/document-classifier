# document-classifier

Python based document classifier: classifies pages of HR documents against a category CSV using offline text extraction plus rule-based keyword and similarity scoring. No LLM, no embedding model, no training (see `docs/adr/`).

Spec: [#1](https://github.com/rohangarg121993/document-classifier/issues/1).

## Setup

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Usage

```sh
uv run python -m docclassifier classify path/to/file.pdf --page 2 --categories config/categories.csv
```

Options:

- `--settings my.toml`: override any of the defaults in `src/docclassifier/default_settings.toml`
- `--include-text`: include the extracted page text in the output (off by default: page text is personal data)

From Python:

```python
from docclassifier import classify, extract_page, load_categories, load_settings

settings = load_settings()
page = extract_page("file.pdf", 2, settings)
result = classify(page, load_categories("config/categories.csv"), settings)
```

## Tests

```sh
uv run python -m pytest
```

> `python -m …` is used instead of the `docclassify` / `pytest` launchers because some managed Windows machines block executables inside `.venv\Scripts`.

## Data protection

This repo is public. Never commit real documents, OCR caches, review/label files or outputs. `.gitignore` blocks them by default (ADR-0001).
