# 0002: Offline OCR, rule-based classification, no LLM or embedding models

**Status:** Accepted (2026-10-26). The classification part is superseded by ADR-0005, which adds an offline sentence encoder; still no LLM and no training.

## Context

Pages must be classified into ~144 HR document categories without labelled training data, and the pages contain personal data.

## Decision

- **Classification** is rule-based and transparent: keyword matching (synonyms, positive and negative phrases) plus character n-gram TF-IDF similarity against category profiles, combined with configurable region and signal weights. No LLM, no embedding model, no trained classifier. TF-IDF is fitted on the category CSV only.
- **OCR** runs offline. v1 uses Tesseract (plus native PDF text when present) behind a small, swappable engine interface.
- **Handwriting:** v1 detects and flags mostly-handwritten pages rather than reading them. A future handwriting engine may use pretrained, offline, non-LLM models (e.g. EasyOCR, TrOCR) as an optional extra.
- **Cloud OCR is not allowed** without a separate data-protection decision: no page leaves the machine.

## Consequences

- Accuracy depends on the quality of the category CSV; `selfcheck` and `evaluate` are the tuning tools.
- Learning weights from collected labels is a possible later step and would need its own ADR.
- Mostly-handwritten pages are routed to human review in v1.
