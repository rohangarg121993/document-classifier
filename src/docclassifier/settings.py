"""Settings: packaged TOML defaults, optionally overridden by a user TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OcrSettings:
    languages: str


@dataclass(frozen=True)
class ClassifierSettings:
    top_n: int
    synonym_weight: float
    phrase_weight: float
    similarity_weight: float
    keyword_cap: float
    negative_penalty: float
    min_prefix_length: int
    min_fuzzy_length: int
    fuzzy_threshold: float
    fuzzy_weight: float
    region_weight_top: float
    region_weight_middle: float
    region_weight_bottom: float
    region_weight_full: float
    min_region_chars: int


@dataclass(frozen=True)
class DecisionSettings:
    confidence_score_weight: float
    confidence_margin_weight: float
    threshold: float
    min_text_chars: int
    fallback_category_id: str


@dataclass(frozen=True)
class Settings:
    ocr: OcrSettings
    classifier: ClassifierSettings
    decision: DecisionSettings


_SECTIONS = {"ocr": OcrSettings, "classifier": ClassifierSettings, "decision": DecisionSettings}


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
