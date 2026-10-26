# 0001: No documents or personal data in the public repo

**Status:** Accepted (2026-10-26)

## Context

The repository `rohangarg121993/document-classifier` is public. The tool classifies pages from HR personnel files (contracts, sick notes, warnings, salary documents), which contain personal and often special-category data under GDPR. Anything committed to a public repo is effectively published permanently: history and forks keep it even after deletion.

## Decision

The repo stays public. It contains code, configuration, the category taxonomy (`categories.csv`), tests, synthetic fixtures and documentation.

It never contains:

- real documents or page images,
- the OCR cache (extracted page text),
- review / label files (they carry file names, which often include employee names, and per-page predictions),
- classifier outputs.

These are excluded via `.gitignore`. Tests use synthetic pages generated from the category CSV or hand-written fixture text. Logs record only IDs and scores, never page text; page text appears in output only with an explicit `--include-text` flag.

## Consequences

- There is no shared labelled dataset in the repo; each user keeps labels locally.
- Test fixtures must be synthetic or fully anonymised.
- Image/PDF file types are ignored by default; fixtures under `tests/fixtures/` are explicitly re-included and must be synthetic.
