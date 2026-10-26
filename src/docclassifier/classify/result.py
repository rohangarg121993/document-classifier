"""Classification output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class KeywordMatch:
    """A keyword found on the page. Holds the CSV keyword, never the page text (ADR-0001)."""

    keyword: str
    kind: Literal["exact", "prefix", "fuzzy"]
    weight: float  # specificity × (1 for exact/prefix, fuzzy_weight for fuzzy)


@dataclass(frozen=True)
class Candidate:
    category_id: str
    category_name: str
    parent_category: str
    score: float
    synonym_score: float = 0.0
    phrase_score: float = 0.0
    similarity: float = 0.0
    negative_penalty: float = 0.0
    matched_synonyms: list[KeywordMatch] = field(default_factory=list)
    matched_phrases: list[KeywordMatch] = field(default_factory=list)
    matched_negatives: list[KeywordMatch] = field(default_factory=list)


@dataclass(frozen=True)
class ClassificationResult:
    status: Literal["classified", "parent_only", "fallback", "unclassified"]
    category_id: str
    category_name: str | None
    parent_category: str | None
    confidence: float
    candidates: list[Candidate]
    reason: Literal["low_confidence", "insufficient_text"] | None = None
    parent_confidence: float | None = None
    # Every category, best first. For API users and tests; not part of the JSON output.
    candidates_all: list[Candidate] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        data = asdict(self)
        del data["candidates_all"]
        return data
