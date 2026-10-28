"""Rule-based document page classifier: offline OCR, then title-first matching against a category CSV."""

from docclassifier.classify import ClassificationResult, classify, load_categories
from docclassifier.ocr import PageText, extract_page
from docclassifier.settings import Settings, load_settings

__all__ = [
    "ClassificationResult",
    "PageText",
    "Settings",
    "classify",
    "extract_page",
    "load_categories",
    "load_settings",
]
