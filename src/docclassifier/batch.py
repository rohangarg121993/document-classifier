"""Batch classification: every page of a file, or of every supported file in a folder."""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from docclassifier import feedback
from docclassifier.classify import CategorySet, classify, load_categories
from docclassifier.ocr import ExtractionError, extract_page, page_count
from docclassifier.ocr.extract import SUPPORTED_SUFFIXES
from docclassifier.settings import Settings


def collect_files(target: str | Path) -> list[Path]:
    """A file as given, or every supported file under a folder (recursively, in sorted order)."""
    path = Path(target)
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    return [path]


def page_record(
    file: Path, page_number: int, categories: CategorySet, settings: Settings, include_text: bool = False
) -> dict:
    """Classify one page into an output record. Extraction problems become an error record, not an exception."""
    started = time.perf_counter()
    try:
        page = extract_page(file, page_number, settings)
    except ExtractionError as exc:
        return error_record(file, page_number, str(exc))
    extracted = time.perf_counter()
    # A page a person already validated keeps their label (ADR-0004).
    result = feedback.validated(page, categories, settings) or classify(page, categories, settings)
    classified = time.perf_counter()

    record = {
        "file": str(file),
        "page": page_number,
        **result.to_dict(),
        "extraction_method": page.method,
        "ocr_quality": page.ocr_quality,
        "handwriting_suspected": page.handwriting_suspected,
        "timings_ms": {"extract": _ms(started, extracted), "classify": _ms(extracted, classified)},
    }
    if include_text:
        record["text"] = page.text
    return record


def error_record(file: Path, page_number: int | None, message: str) -> dict:
    return {"file": str(file), "page": page_number, "status": "error", "error": message}


def classify_all(
    target: str | Path, categories_path: str | Path, settings: Settings, workers: int = 1, include_text: bool = False
) -> Iterator[dict]:
    """Yield one record per page, in file order then page order, whatever the number of workers."""
    # (file, page, error): an unreadable file stays in its place in the output order as one error record.
    tasks: list[tuple[Path, int | None, str | None]] = []
    for file in collect_files(target):
        try:
            tasks.extend((file, n, None) for n in range(1, page_count(file) + 1))
        except ExtractionError as exc:
            tasks.append((file, None, str(exc)))

    if workers <= 1:
        categories = feedback.with_examples(load_categories(categories_path), settings)
        for task in tasks:
            yield _run(task, categories, settings, include_text)
        return

    with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(str(categories_path), settings)) as pool:
        yield from pool.map(_run_in_worker, tasks, [include_text] * len(tasks), chunksize=4)


_worker_state: dict = {}


def _run(task, categories: CategorySet, settings: Settings, include_text: bool) -> dict:
    file, page_number, error = task
    if error is not None:
        return error_record(file, page_number, error)
    try:
        return page_record(file, page_number, categories, settings, include_text)
    except Exception as exc:  # one bad page must not stop a batch
        return error_record(file, page_number, f"{type(exc).__name__}: {exc}")


def _init_worker(categories_path: str, settings: Settings) -> None:
    _worker_state["categories"] = feedback.with_examples(load_categories(categories_path), settings)
    _worker_state["settings"] = settings


def _run_in_worker(task, include_text: bool) -> dict:
    return _run(task, _worker_state["categories"], _worker_state["settings"], include_text)


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 1)
