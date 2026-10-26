"""Classification output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class Candidate:
    category_id: str
    category_name: str
    parent_category: str
    score: float
    matched_synonyms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassificationResult:
    status: Literal["classified", "unclassified"]
    category_id: str
    category_name: str | None
    parent_category: str | None
    confidence: float
    candidates: list[Candidate]

    def to_dict(self) -> dict:
        return asdict(self)
