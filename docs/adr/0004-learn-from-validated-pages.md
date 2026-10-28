# 0004: Learn from pages a person validated

**Status:** Accepted (2026-10-28); learned examples amended by ADR-0005: a page that nearly repeats a validated one (cosine ≥ 0.85) takes its label directly. Amends ADR-0002 ("TF-IDF is fitted on the category CSV only"; learning from labels "would need its own ADR").

## Context

Reviewers already correct predictions in the review file (`classify --review-out`). Those corrections were only used to measure accuracy (`evaluate`); the next run made the same mistakes again. Many HR pages are recurring forms whose CSV definition matches poorly, but whose validated instances look almost identical to the next one.

## Decision

- **`learn REVIEW_CSV`** stores every labelled page of a corrected review file in a local feedback store (`[feedback] dir`, default `.cache/feedback`), keyed by a SHA-256 of the page's normalised text. Running it again adds to the store; re-learning a page overwrites its label.
- **Known page:** when `classify` sees a page whose normalised text is in the store, it returns the stored label with status `validated` and confidence 1.0, without scoring. Matching is by content, so renamed or moved files still match; labels no longer in the category CSV are ignored.
- **Learned examples:** every stored page is an example of its category. Example evidence is the TF-IDF cosine (character 3–5-grams) to the closest example of each category and joins the ADR-0003 doubt product as a fourth signal, `(1 − 0.9 · examples)`. Below cosine 0.6 it is no evidence, from 0.85 it is full evidence. Like profile similarity (ADR-0003), the page's top section is compared with the examples' top sections and weighted 0.6 once it holds 5+ words, so `learn` also stores each page's top section. That vectorizer is fitted on the category profiles plus the examples; the profile similarity itself stays fitted on the CSV only.
- Still no LLM, no embedding model and no trained weights: the result stays explainable, since `example_similarity` is reported per candidate.

## Consequences

- The store holds normalised page text, which is personal data: it lives under the git-ignored `.cache/` and never leaves the machine (ADR-0001). Deleting the directory forgets everything.
- A wrong label in a review file is repeated for that page and pulls similar pages towards it. Fix it in the review file and run `learn` again.
- `evaluate` on pages that were already learned returns their stored labels and so overstates accuracy. Measure on pages that were not learned, or with `[feedback] enabled = false`.
- The floor, full and reliability values were measured on synthetic forms (same form, other person ≈ 0.9; another form ≈ 0.65; unrelated pages ≈ 0.15). Calibrate them with `evaluate` on real pages that were not learned.
