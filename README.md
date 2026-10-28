# document-classifier

Python based document classifier: classifies pages of HR documents against a category CSV using offline text extraction (embedded PDF text or Tesseract OCR) then reads it the way a person does: find the title, match it against the category synonyms, and judge the content only when the title isn't enough. Content is compared by meaning with a small offline sentence encoder shipped in `models/`, plus the categories' positive and negative phrases. No LLM, no training, nothing leaves the machine (see `docs/adr/`).

Spec: [#1](https://github.com/rohangarg121993/document-classifier/issues/1).

## Setup

Requires Python ≥ 3.10 and, for scanned pages, [Tesseract](https://github.com/tesseract-ocr/tesseract) with the `deu` and `eng` language data. Nothing else: no uv, no virtual environment, and the classifier itself is not installed. It runs from the checkout via `docclassify.py`.

```sh
python -m pip install --user -r requirements.txt
```

`requirements.txt` pins the exact versions from `uv.lock`. Drop `--user` to install for all users (admin shell). On Windows, use `py -3.10 -m pip …` / `py -3.10 docclassify.py …` to pick a specific Python.

The text encoder (`models/multilingual-e5-small`, about 135 MB) comes with the repository; nothing is downloaded at run time. If it is missing or damaged, `classify` stops with a message instead of guessing.

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

## How a page is classified

Title first, content second (ADR-0005):

1. **Validated before?** A page `learn` stored, or one that nearly repeats it (same form, other person), keeps that label.
2. **Find the title:** the `Betreff:` line, else the line before "Sehr geehrte…", else large print near the top, else a short line without digits (a bold title in body print, a form's type label). A letterhead that names no category is skipped.
3. **Match the title against the synonyms.** German compounds count by their last part ("Verhaltensabmahnung" → Abmahnung), but a short prefix doesn't make a compound ("Abrechnung" is no Rechnung). The most specific name wins ("Zwischenzeugnis" over "Zeugnis"). Exactly one match, and no sibling fits the content clearly better → classified, confidence 0.9.
4. **Otherwise the content decides:** meaning (cosine to the category's name, description and positive phrases) + positive phrases found by word stem − negative phrases found. A negative phrase in the title rules the category out. A clear lead (0.02) → classified, confidence 0.6; siblings too close to call → `parent_only`; else UNCLASSIFIED.

Too little text, suspected handwriting (confidence capped at 0.45) and the optional fallback category apply on top. Every result reports the `title` line that decided it. Every number is a setting in `default_settings.toml`.

Because synonyms are matched against titles, they should be what documents of the category are *titled*; descriptions and phrases say what their body *says*. `docs/taxonomy-review.md` lists how `config/categories.csv` was cleaned for this (merged duplicates, title-style synonyms) and the definitions still waiting for business input.

## Tests

```sh
python -m pip install --user -r requirements-dev.txt
python -m pytest
```

Tests marked `tesseract` are skipped when the Tesseract binary is missing, tests marked `encoder` when `models/` is. CI runs the full suite with Tesseract, plus `selfcheck` on `config/categories.csv`.

> `python docclassify.py` / `python -m pytest` are used instead of `.exe` launchers because some managed Windows machines block them.

## Data protection

This repo is public. Never commit real documents, OCR caches (`.cache/`), review/label files or outputs. `.gitignore` blocks them by default (ADR-0001).
