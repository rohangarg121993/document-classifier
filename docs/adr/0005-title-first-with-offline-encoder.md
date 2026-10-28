# 0005: Classify by the title first, the content second, with an offline sentence encoder

**Status:** Accepted (2026-10-28). Supersedes ADR-0003 and the "no embedding model" part of ADR-0002; amends ADR-0004.

## Context

The evidence model of ADR-0003 counted every keyword wherever it appeared and averaged weak signals over the whole page. On real pages most results came out UNCLASSIFIED, and on 50 realistic synthetic first pages only 15 were classified correctly while 8 were confidently wrong. Two causes dominated:

- documents mention other document types ("…müssen Sie mit einer Kündigung rechnen"), and those mentions competed with the actual title;
- character n-gram TF-IDF cannot tell that "endet im gegenseitigen Einvernehmen" describes an Aufhebungsvertrag.

A person reads a page differently: they look at the title, and read the body only when the title isn't enough.

## Decision

1. **Find the title**, in the order a reader looks: the `Betreff:` line; the line before the salutation (DIN 5008); large print in the upper half; short lines without digits at the top, then anywhere (a title in bold body print, a form's type label). The first candidate that names a category is the title, so a letterhead is skipped.
2. **Match the title against the synonyms.** A synonym names the title as whole words, or as the last part of a German compound whose first part is a word of at least 4 letters ("Verhaltensabmahnung" is an Abmahnung; "Abrechnung" is not a Rechnung). The most specific match wins ("Zwischenzeugnis", not "Zeugnis").
3. **Let the content decide** when the title names no category or names several, and between the named category and its siblings (same parent). Score = cosine to the category's name, description and positive phrases + phrase weight × positive phrases found (by word stems) − negative weight × negative phrases found. A negative phrase in the title rules a category out. A single title match is overruled only by a sibling that leads clearly (`min_margin`); otherwise the title wins.
4. **The cosine comes from multilingual-e5-small** (quantised ONNX, 118 MB, run with `onnxruntime` on the CPU). It is a pretrained sentence encoder: it is not trained on our documents, generates nothing, and is not an LLM. It ships in `models/` (MIT licence), split into parts below GitHub's file size limit and checked by SHA-256 when loaded.
5. **Decisions:** title match → confidence 0.9; content alone → 0.6 when the leader is ahead by `min_margin`; siblings closer than that → `parent_only`; otherwise UNCLASSIFIED. Too little text, suspected handwriting, the threshold and the fallback category apply as before.
6. **Validated pages (ADR-0004):** a page that nearly repeats a page validated with `learn` (character n-gram cosine ≥ 0.85) takes its label before any title matching.

## Consequences

- On the 50-page benchmark: 33 correct (was 15), 6 confidently wrong (was 8), right answer in the top 3 for 42. The benchmark is synthetic; real scans still need measuring with `evaluate`.
- The synonyms column now means "how documents of this category are titled". Generic synonyms ("Bescheinigung", "Zeugnis") send titles to the wrong category, so the taxonomy matters more than before; `docs/taxonomy-review.md` proposes a cleaned CSV.
- The repository grows by about 135 MB for the model. Installing needs `onnxruntime`, `tokenizers` and `snowballstemmer`, all with wheels for Windows and Python 3.10–3.13.
- Page text still never leaves the machine, and logs carry IDs and scores only (ADR-0001).
