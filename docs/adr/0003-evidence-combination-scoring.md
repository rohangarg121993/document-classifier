# 0003: Combine evidence instead of averaging it

**Status:** Accepted (2026-10-26). Replaces the region-split scoring of #6 and the confidence formula of #7.

## Context

The first scoring model averaged weighted signals per page region and blended score with margin for confidence. On real pages it classified correctly but with confidence around 0.2–0.45, often below the threshold:

- a weighted average reaches 1 only when every signal is maxed out, which real pages never do;
- splitting the page into thirds diluted evidence spread across the page;
- a single title synonym counted as one third of full evidence (shared cap of 3);
- similarity was judged against 1.0 although real matching pages reach about 0.5.

## Decision

- **Strength** per category: each signal removes part of the remaining doubt,
  `1 − (1 − 0.95·synonyms)(1 − 0.60·phrases)(1 − 0.50·similarity) − 0.15·negatives`.
- **Synonyms are titles.** One synonym is full evidence at the top of the page, 0.30 in the middle and 0.20 at the bottom. Shared synonyms are **not** discounted: a title shared by two siblings is still strong evidence against unrelated categories, and the tie is left to the decision layer (parent fallback). We measured discounting them, and it was worse on every check.
- **Phrases** keep the cap of 3, the specificity discount and fuzzy weighting, plus position factors 1.0 / 0.8 / 0.7.
- **Page position is a per-hit factor**, not a split. Evidence is gathered on the whole page. Per-category `weight_top/middle/bottom` CSV columns override the factors.
- **Similarity** counts as full evidence at cosine 0.5.
- **Confidence** = `s1 · (1 − (1 − s1) / (1 − s2))`: winner strength times how much less doubt it leaves than the runner-up. Default threshold 0.50; the handwriting cap is 0.45.

## Consequences

- Clear pages score 0.85–0.98; unrelated pages stay near 0; sibling ties give `parent_only`.
- Categories that share title synonyms with a sibling (12 in the current taxonomy, e.g. FIN02/FIN04, URK01/URK10) can only be told apart by their phrases and are often returned as `parent_only`. The fix belongs in the taxonomy; `selfcheck` lists them, and CI guards the current count.
- All weights are untuned guesses checked on synthetic pages; calibrate with `evaluate` on reviewed real pages.
