"""Classifier module: score a page's text against the category taxonomy."""

from docclassifier.classify.categories import Category, CategoryFileError, CategorySet, load_categories
from docclassifier.classify.classifier import classify
from docclassifier.classify.result import Candidate, ClassificationResult

__all__ = [
    "Candidate",
    "Category",
    "CategoryFileError",
    "CategorySet",
    "ClassificationResult",
    "classify",
    "load_categories",
]
