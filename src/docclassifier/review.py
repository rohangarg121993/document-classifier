"""Review files and evaluation: labelled data is built from normal use, not a separate labelling project.

`classify --review-out` writes one row per page with the prediction pre-filled as the expected label; a person
corrects only the wrong rows, and `evaluate` measures accuracy against that file. Review files hold file names
and per-page predictions, which count as personal data: keep them out of git (ADR-0001).
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

REVIEW_COLUMNS = ["file", "page", "predicted_id", "confidence", "top3", "expected_category_id"]


class ReviewWriter:
    def __init__(self, path: str | Path):
        self._fh = open(path, "w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=REVIEW_COLUMNS)
        self._writer.writeheader()

    def write(self, record: dict) -> None:
        predicted = "" if record.get("status") == "error" else record["category_id"]
        self._writer.writerow(
            {
                "file": record["file"],
                "page": record["page"] if record["page"] is not None else "",
                "predicted_id": predicted,
                "confidence": record.get("confidence", ""),
                "top3": format_top3(record.get("candidates", [])),
                "expected_category_id": predicted,
            }
        )

    def close(self) -> None:
        self._fh.close()


def format_top3(candidates: list[dict]) -> str:
    return "; ".join(f"{c['category_id']}:{c['score']:.3f}" for c in candidates[:3])


def read_labels(path: str | Path) -> list[tuple[Path, int, str]]:
    """(file, page, expected) rows from a label file or corrected review file; blank labels are skipped.
    Relative file paths resolve against the label file's folder."""
    path = Path(path)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = {"file", "page", "expected_category_id"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing column(s) {', '.join(sorted(missing))}")
        rows = []
        for row in reader:
            expected = (row["expected_category_id"] or "").strip()
            if not expected or not (row["page"] or "").strip():
                continue
            file = Path(row["file"])
            rows.append((file if file.is_absolute() else path.parent / file, int(row["page"]), expected))
    return rows


def evaluation_report(results: Iterable[tuple[Path, int, str, dict]]) -> dict:
    """`results` holds (file, page, expected, classification record) per labelled page."""
    confusion: dict[str, Counter] = {}
    misclassified = []
    total = correct = 0
    for file, page, expected, record in results:
        predicted = "ERROR" if record.get("status") == "error" else record["category_id"]
        total += 1
        correct += predicted == expected
        confusion.setdefault(expected, Counter())[predicted] += 1
        if predicted != expected:
            misclassified.append(
                {
                    "file": str(file),
                    "page": page,
                    "expected": expected,
                    "predicted": predicted,
                    "confidence": record.get("confidence"),
                    "top3": [
                        {"category_id": c["category_id"], "score": c["score"]} for c in record.get("candidates", [])[:3]
                    ],
                }
            )
    return {
        "summary": {"pages": total, "correct": correct, "accuracy": round(correct / total, 4) if total else 0.0},
        "confusion": {expected: dict(counts) for expected, counts in sorted(confusion.items())},
        "misclassified": misclassified,
    }


def format_evaluation(report: dict) -> str:
    s = report["summary"]
    lines = [f"accuracy {s['accuracy'] * 100:.1f}% ({s['correct']}/{s['pages']} pages)"]
    if report["misclassified"]:
        lines += ["", "misclassified:"]
        for m in report["misclassified"]:
            top = ", ".join(f"{c['category_id']} {c['score']:.2f}" for c in m["top3"])
            lines.append(f"  {m['file']} p{m['page']}: expected {m['expected']}, got {m['predicted']}  [{top}]")
        lines += ["", "confusion (expected -> predicted: pages):"]
        for expected, counts in report["confusion"].items():
            for predicted, n in counts.items():
                if predicted != expected:
                    lines.append(f"  {expected} -> {predicted}: {n}")
    return "\n".join(lines)
