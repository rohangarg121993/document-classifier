"""Run the classifier straight from a checkout, without installing it: python docclassify.py classify ..."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from docclassifier.cli import main  # noqa: E402

# Guarded: with --workers on Windows, each worker process re-imports this file.
if __name__ == "__main__":
    raise SystemExit(main())
