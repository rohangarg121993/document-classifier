"""On-disk cache of OCR results, so re-running the classifier while tuning doesn't repeat slow OCR.

Entries hold extracted page text, which is personal data: the cache lives in a git-ignored directory and stays
on the local machine (ADR-0001). The key covers the file contents, the page number and every setting that
changes OCR output, so editing the file or the OCR settings never serves a stale entry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from docclassifier.ocr.models import PageText, Word
from docclassifier.settings import Settings


def cache_key(path: Path, page_number: int, settings: Settings) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    ocr = settings.ocr
    digest.update(f"|{page_number}|{ocr.engine}|{ocr.languages}|{ocr.dpi}".encode())
    return digest.hexdigest()


def load(key: str, settings: Settings) -> PageText | None:
    path = _entry(key, settings)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    words = [Word(**{**w, "line": tuple(w["line"]) if w["line"] is not None else None}) for w in data.pop("words")]
    return PageText(words=words, **data)


def store(key: str, page: PageText, settings: Settings) -> None:
    path = _entry(key, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(page), ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)  # atomic, so parallel workers never read half-written entries


def _entry(key: str, settings: Settings) -> Path:
    return Path(settings.cache.dir) / key[:2] / f"{key}.json"
