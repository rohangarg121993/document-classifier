"""Keyword matching against normalised page text.

Rules (all lengths are of the normalised keyword):
- every keyword matches as a whole word or phrase ("exact");
- keywords of `min_prefix_length`+ characters also match at the start of a longer word, which covers German
  compounds such as "abmahnung" in "abmahnungsschreiben" ("prefix");
- keywords of `min_fuzzy_length`+ characters also match a window of the same number of words with a
  similarity ratio of at least `fuzzy_threshold`, tolerating OCR errors ("fuzzy").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz, process

MatchKind = Literal["exact", "prefix", "fuzzy"]


@dataclass(frozen=True)
class MatchRules:
    min_prefix_length: int
    min_fuzzy_length: int
    fuzzy_threshold: float


class PageMatcher:
    """Matches keywords against one page's normalised text; caches per-page lookups."""

    def __init__(self, normalized_text: str, rules: MatchRules):
        self._padded = f" {normalized_text} "
        self._tokens = normalized_text.split()
        self._rules = rules
        self._windows: dict[int, list[str]] = {}

    def match(self, keyword: str) -> MatchKind | None:
        """`keyword` must already be normalised."""
        if not keyword:
            return None
        if f" {keyword} " in self._padded:
            return "exact"
        if len(keyword) >= self._rules.min_prefix_length and f" {keyword}" in self._padded:
            return "prefix"
        if len(keyword) >= self._rules.min_fuzzy_length and self._fuzzy(keyword):
            return "fuzzy"
        return None

    def _fuzzy(self, keyword: str) -> bool:
        n_words = keyword.count(" ") + 1
        candidates = self._windows_of(n_words)
        hit = process.extractOne(keyword, candidates, scorer=fuzz.ratio, score_cutoff=self._rules.fuzzy_threshold)
        return hit is not None

    def _windows_of(self, n_words: int) -> list[str]:
        if n_words not in self._windows:
            tokens = self._tokens
            self._windows[n_words] = list(
                dict.fromkeys(" ".join(tokens[i : i + n_words]) for i in range(len(tokens) - n_words + 1))
            )
        return self._windows[n_words]

