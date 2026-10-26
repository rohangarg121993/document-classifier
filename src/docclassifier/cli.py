"""Command-line interface.

    docclassify classify FILE --page N --categories CSV     one page → pretty JSON
    docclassify classify FILE_OR_FOLDER --categories CSV    every page → JSON Lines
    docclassify selfcheck --categories CSV                  can each category recognise its own synthetic page?
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from docclassifier.batch import classify_all, page_record
from docclassifier.classify import CategoryFileError, load_categories
from docclassifier.selfcheck import format_report, selfcheck
from docclassifier.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docclassify", description="Classify document pages against a category CSV.")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("classify", help="classify one page, every page of a file, or every file in a folder")
    cmd.add_argument("target", metavar="FILE_OR_FOLDER")
    cmd.add_argument("--page", type=int, help="page number, starting at 1 (default: every page, as JSON Lines)")
    cmd.add_argument("--categories", required=True, help="category CSV file")
    cmd.add_argument("--settings", help="TOML file overriding default settings")
    cmd.add_argument("--include-text", action="store_true", help="include the page text in the output")
    cmd.add_argument("--no-cache", action="store_true", help="don't read or write the OCR cache")
    cmd.add_argument("--force-ocr", action="store_true", help="OCR even when a PDF page has embedded text")
    cmd.add_argument("--workers", type=int, default=1, help="parallel worker processes for batches (default 1)")
    check = sub.add_parser("selfcheck", help="check each category against a synthetic page built from its definition")
    check.add_argument("--categories", required=True, help="category CSV file")
    check.add_argument("--settings", help="TOML file overriding default settings")
    check.add_argument("--min-margin", type=float, default=0.05, help="lead over the runner-up needed to pass")
    check.add_argument("--max-failures", type=int, default=0, help="exit non-zero only above this many failures")
    check.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)

    settings = load_settings(args.settings)
    if args.command == "selfcheck":
        return _selfcheck(args, settings)
    if args.no_cache:
        settings = replace(settings, cache=replace(settings.cache, enabled=False))
    if args.force_ocr:
        settings = replace(settings, ocr=replace(settings.ocr, force_ocr=True))
    try:
        categories = load_categories(args.categories)
    except CategoryFileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")

    target = Path(args.target)
    if args.page is not None:
        if target.is_dir():
            parser.error("--page needs a file, not a folder")
        record = page_record(target, args.page, categories, settings, args.include_text)
        if record.get("status") == "error":
            print(f"error: {record['error']}", file=sys.stderr)
            return 2
        json.dump({**record, "file": args.target}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    failures = 0
    for record in classify_all(target, args.categories, settings, args.workers, args.include_text):
        failures += record.get("status") == "error"
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 1 if failures else 0


def _selfcheck(args, settings) -> int:
    try:
        categories = load_categories(args.categories)
    except CategoryFileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = selfcheck(categories, settings, args.min_margin)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_report(report))
    return 1 if report["summary"]["failed"] > args.max_failures else 0
