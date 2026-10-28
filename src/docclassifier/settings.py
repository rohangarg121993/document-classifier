"""Settings: packaged TOML defaults, optionally overridden by a user TOML file."""

from __future__ import annotations

import sys
from dataclasses import dataclass, fields
from importlib import resources
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: same API, from the tomli backport
    import tomli as tomllib


@dataclass(frozen=True)
class OcrSettings:
    engine: str
    languages: str
    tesseract_cmd: str
    dpi: int
    force_ocr: bool
    min_native_chars: int
    min_ink_ratio: float
    handwriting_min_word_confidence: float
    handwriting_unrecognised_ink: float
    low_quality_mean_confidence: float


@dataclass(frozen=True)
class ClassifierSettings:
    top_n: int
    heading_ratio: float
    min_compound_length: int
    title_match_confidence: float
    phrase_cap: float
    similarity_top_share: float
    similarity_top_min_words: int
    example_confidence: float
    example_similarity: float


@dataclass(frozen=True)
class DecisionSettings:
    threshold: float
    min_text_chars: int
    fallback_category_id: str
    handwriting_confidence_cap: float


@dataclass(frozen=True)
class CacheSettings:
    enabled: bool
    dir: str


@dataclass(frozen=True)
class ContextSettings:
    enabled: bool
    model_dir: str
    min_margin: float
    confidence: float
    phrase_weight: float
    sibling_phrase_weight: float
    negative_weight: float


@dataclass(frozen=True)
class FeedbackSettings:
    enabled: bool
    dir: str


@dataclass(frozen=True)
class Settings:
    ocr: OcrSettings
    cache: CacheSettings
    classifier: ClassifierSettings
    decision: DecisionSettings
    feedback: FeedbackSettings
    context: ContextSettings


_SECTIONS = {
    "ocr": OcrSettings,
    "cache": CacheSettings,
    "classifier": ClassifierSettings,
    "decision": DecisionSettings,
    "feedback": FeedbackSettings,
    "context": ContextSettings,
}


def load_settings(path: str | Path | None = None) -> Settings:
    """Load the packaged defaults, then apply overrides from `path` if given.

    Unknown sections or keys raise ValueError so typos don't silently fall back to defaults.
    """
    defaults = resources.files("docclassifier").joinpath("default_settings.toml").read_text("utf-8")
    data = tomllib.loads(defaults)
    if path is not None:
        with open(path, "rb") as fh:
            _merge(data, tomllib.load(fh))
    return Settings(**{name: cls(**data[name]) for name, cls in _SECTIONS.items()})


def _merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for section, values in override.items():
        if section not in _SECTIONS:
            raise ValueError(f"Unknown settings section [{section}]")
        allowed = {f.name for f in fields(_SECTIONS[section])}
        for key, value in values.items():
            if key not in allowed:
                raise ValueError(f"Unknown setting [{section}].{key}")
            base[section][key] = value
