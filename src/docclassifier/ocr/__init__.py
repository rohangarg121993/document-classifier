"""OCR module: turn one page of a document into text with word positions."""

from docclassifier.ocr.extract import ExtractionError, extract_page, page_count
from docclassifier.ocr.models import PageText, Word

__all__ = ["ExtractionError", "PageText", "Word", "extract_page", "page_count"]
