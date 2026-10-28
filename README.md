# document-classifier

Python based document classifier: classifies pages of HR documents against a category CSV using offline text extraction (embedded PDF text or Tesseract OCR) plus rule-based keyword, similarity and page-region scoring. No LLM, no embedding model, no training (see `docs/adr/`).

Spec: [#1](https://github.com/rohangarg121993/document-classifier/issues/1).

## Setup

Requires Python ≥ 3.10 and, for scanned pages, [Tesseract](https://github.com/tesseract-ocr/tesseract) with the `deu` and `eng` language data. Nothing else: no uv, no virtual environment, and the classifier itself is not installed. It runs from the checkout via `docclassify.py`.

```sh
python -m pip install --user -r requirements.txt
```

`requirements.txt` pins the exact versions from `uv.lock`. Drop `--user` to install for all users (admin shell). On Windows, use `py -3.10 -m pip …` / `py -3.10 docclassify.py …` to pick a specific Python.

Offline target machine: on a connected machine with the **same Python version and OS**, run `python -m pip download -r requirements.txt -d wheels`, copy `wheels/` over with the repo, then `python -m pip install --user --no-index --find-links wheels -r requirements.txt`.

Developing with [uv](https://docs.astral.sh/uv/) also works (`uv sync`, `python docclassify.py …`). After changing dependencies, regenerate the requirements with `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`.

Tesseract is found via the `[ocr].tesseract_cmd` setting, then the `TESSERACT_CMD` environment variable, then `PATH`, then `C:\Program Files\Tesseract-OCR\tesseract.exe`.

## Usage

```sh
# One page → JSON
python docclassify.py classify scan.pdf --page 2 --categories config/categories.csv

# Every page of a file, or every PDF/PNG/JPG/TIFF in a folder → JSON Lines
python docclassify.py classify inbox/ --categories config/categories.csv --workers 4

# Same, and write a review file with predictions pre-filled as labels
python docclassify.py classify inbox/ --categories config/categories.csv --review-out review.csv

# After correcting the wrong rows in review.csv: accuracy, confusion, misclassified pages
python docclassify.py evaluate review.csv --categories config/categories.csv

# Remember the validated labels: later runs return them for these pages and classify similar pages alike
python docclassify.py learn review.csv

# Can every category recognise a synthetic page built from its own definition? (no labelled data needed)
python docclassify.py selfcheck --categories config/categories.csv
```

`classify` options: `--settings my.toml` (override any default in `src/docclassifier/default_settings.toml`), `--include-text` (add page text to the output; off by default), `--no-cache`, `--force-ocr`, `--workers N`, `--review-out CSV`.

Each result has `status`:
- `classified`: a category was found.
- `parent_only`: the parent category is clear but the child isn't.
- `fallback`: no category was found and `fallback_category_id` is set, so that category is used.
- `unclassified`: no category was found; `reason` is `low_confidence` or `insufficient_text`.
- `validated`: a person already labelled this page (same text) and `learn` stored it; the label is returned as is.

`learn` keeps validated pages in `.cache/feedback` (page text: stays local, ADR-0001); delete the folder to forget them, or set `[feedback] enabled = false`. Run `evaluate` on pages that were not learned, otherwise it reports their stored labels (ADR-0004).

Each result also has a confidence, the top-3 candidates with a per-region score breakdown, the extraction method, and `ocr_quality` / `handwriting_suspected` flags.

From Python:

```python
import sys
sys.path.insert(0, "src")  # the classifier isn't installed; run from the repo root

from docclassifier import classify, extract_page, load_categories, load_settings

settings = load_settings()
page = extract_page("file.pdf", 2, settings)
result = classify(page, load_categories("config/categories.csv"), settings)
```

## How scoring works

Each category collects independent evidence, and every signal removes part of the remaining doubt (ADR-0003):

```text
strength   = 1 − (1 − 0.95·synonyms)(1 − 0.60·phrases)(1 − 0.50·similarity) − 0.15 × negative hits
confidence = strength × (1 − doubt of winner / doubt of runner-up)      doubt = 1 − strength
             below 0.50 → UNCLASSIFIED, or parent_only when the parent category is clear
```

- **Synonyms** are document-type names. One synonym is full evidence when it's the title: top third, or large print anywhere. A mere mention further down counts 0.5 or 0.4, but only when another document type is the title. On pages without a title (permits, ID documents, forms), the best-placed name counts fully.
- **Phrases** count distinct hits, and three are full evidence. Hits further down the page count a little less (0.8 in the middle, 0.7 at the bottom). Long keywords also match German compounds and OCR misspellings (the misspellings count 0.7×). Phrases shared by many categories count less.
- **Similarity** is TF-IDF on character n-grams against the category profile; a cosine of 0.5 counts as full evidence.

Every number is a setting in `default_settings.toml`.

## Tests

```sh
python -m pip install --user -r requirements-dev.txt
python -m pytest
```

Tests marked `tesseract` are skipped when the Tesseract binary is missing. CI runs the full suite with Tesseract, plus `selfcheck` on `config/categories.csv`.

> `python docclassify.py` / `python -m pytest` are used instead of `.exe` launchers because some managed Windows machines block them.

## Data protection

This repo is public. Never commit real documents, OCR caches (`.cache/`), review/label files or outputs. `.gitignore` blocks them by default (ADR-0001).
