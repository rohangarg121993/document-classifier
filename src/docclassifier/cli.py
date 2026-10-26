"""Command-line interface: `docclassify classify FILE --page N --categories CSV`."""

from __future__ import annotations

import argparse
import json
import sys
import time

from docclassifier.classify import classify, load_categories
from docclassifier.ocr import ExtractionError, extract_page
from docclassifier.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docclassify", description="Classify document pages against a category CSV.")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("classify", help="classify one page of a document")
    cmd.add_argument("file")
    cmd.add_argument("--page", type=int, required=True, help="page number, starting at 1")
    cmd.add_argument("--categories", required=True, help="category CSV file")
    cmd.add_argument("--settings", help="TOML file overriding default settings")
    cmd.add_argument("--include-text", action="store_true", help="include the page text in the output")
    args = parser.parse_args(argv)

    settings = load_settings(args.settings)
    categories = load_categories(args.categories)

    started = time.perf_counter()
    try:
        page = extract_page(args.file, args.page, settings)
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    extracted = time.perf_counter()
    result = classify(page, categories, settings)
    classified = time.perf_counter()

    out = {
        "file": args.file,
        "page": args.page,
        **result.to_dict(),
        "extraction_method": page.method,
        "timings_ms": {"extract": _ms(started, extracted), "classify": _ms(extracted, classified)},
    }
    if args.include_text:
        out["text"] = page.text
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 1)
