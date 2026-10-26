"""Settings: packaged TOML defaults, optionally overridden by a user TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from importlib import resources
from pathlib import Path
from typing import Any


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
    synonym_reliability: float
    phrase_reliability: float
    similarity_reliability: float
    synonym_cap: float
    phrase_cap: float
    similarity_full: float
    negative_penalty: float
    synonym_position_top: float
    synonym_position_middle: float
    synonym_position_bottom: float
    phrase_position_top: float
    phrase_position_middle: float
    phrase_position_bottom: float
    min_prefix_length: int
    min_fuzzy_length: int
    fuzzy_threshold: float
    fuzzy_weight: float


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
class Settings:
    ocr: OcrSettings
    cache: CacheSettings
    classifier: ClassifierSettings
    decision: DecisionSettings


_SECTIONS = {
    "ocr": OcrSettings,
    "cache": CacheSettings,
    "classifier": ClassifierSettings,
    "decision": DecisionSettings,
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
