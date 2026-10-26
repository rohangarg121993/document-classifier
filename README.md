# document-classifier

Python based document classifier: classifies pages of HR documents against a category CSV using offline text extraction (embedded PDF text or Tesseract OCR) plus rule-based keyword, similarity and page-region scoring. No LLM, no embedding model, no training (see `docs/adr/`).

Spec: [#1](https://github.com/rohangarg121993/document-classifier/issues/1).

## Setup

Requires Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) and, for scanned pages, [Tesseract](https://github.com/tesseract-ocr/tesseract) with the `deu` and `eng` language data.

```sh
uv sync
```

Tesseract is found via the `[ocr].tesseract_cmd` setting, then the `TESSERACT_CMD` environment variable, then `PATH`, then `C:\Program Files\Tesseract-OCR\tesseract.exe`.

## Usage

```sh
# One page → JSON
uv run python -m docclassifier classify scan.pdf --page 2 --categories config/categories.csv

# Every page of a file, or every PDF/PNG/JPG/TIFF in a folder → JSON Lines
uv run python -m docclassifier classify inbox/ --categories config/categories.csv --workers 4

# Same, and write a review file with predictions pre-filled as labels
uv run python -m docclassifier classify inbox/ --categories config/categories.csv --review-out review.csv

# After correcting the wrong rows in review.csv: accuracy, confusion, misclassified pages
uv run python -m docclassifier evaluate review.csv --categories config/categories.csv

# Can every category recognise a synthetic page built from its own definition? (no labelled data needed)
uv run python -m docclassifier selfcheck --categories config/categories.csv
```

`classify` options: `--settings my.toml` (override any default in `src/docclassifier/default_settings.toml`), `--include-text` (add page text to the output; off by default), `--no-cache`, `--force-ocr`, `--workers N`, `--review-out CSV`.

Each result has `status`:
- `classified`: a category was found.
- `parent_only`: the parent category is clear but the child isn't.
- `fallback`: no category was found and `fallback_category_id` is set, so that category is used.
- `unclassified`: no category was found; `reason` is `low_confidence` or `insufficient_text`.

Each result also has a confidence, the top-3 candidates with a per-region score breakdown, the extraction method, and `ocr_quality` / `handwriting_suspected` flags.

From Python:

```python
from docclassifier import classify, extract_page, load_categories, load_settings

settings = load_settings()
page = extract_page("file.pdf", 2, settings)
result = classify(page, load_categories("config/categories.csv"), settings)
```

## How scoring works

For each category and each page region (top, middle and bottom thirds, plus the full page):

```text
region score   = 0.35 × synonym evidence + 0.25 × phrase evidence + 0.40 × TF-IDF similarity
category score = region-weighted average (0.40 / 0.20 / 0.15 / 0.25) − 0.15 × negative-phrase hits
confidence     = 0.7 × top score + 0.3 × (top − second)      → below 0.30: UNCLASSIFIED
```

Keyword evidence counts distinct hits, capped at 3. Keywords of 6 or more characters also match German compounds and OCR misspellings (the misspellings count 0.7×). Keywords shared by many categories count less. Every number is a setting.

## Tests

```sh
uv run python -m pytest
```

Tests marked `tesseract` are skipped when the Tesseract binary is missing. CI runs the full suite with Tesseract, plus `selfcheck` on `config/categories.csv`.

> `python -m …` is used instead of the `docclassify` / `pytest` launchers because some managed Windows machines block executables inside `.venv\Scripts`.

## Data protection

This repo is public. Never commit real documents, OCR caches (`.cache/`), review/label files or outputs. `.gitignore` blocks them by default (ADR-0001).
