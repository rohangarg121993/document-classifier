"""Contextual match (ADR-0005): how close a page's meaning is to each category's definition.

A small pretrained multilingual sentence encoder (multilingual-e5-small, quantised ONNX) turns the page and each
category's name, description and positive phrases into vectors; their cosine says how alike they are in meaning,
so "endet im gegenseitigen Einvernehmen" lands near a Aufhebungsvertrag description without sharing its words.
No LLM, nothing generated, nothing trained here; it runs offline on the CPU and page text never leaves the machine.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from weakref import WeakKeyDictionary

import numpy as np

from docclassifier.classify.categories import CategorySet

REPO_ROOT = Path(__file__).resolve().parents[3]
MAX_TOKENS = 512

_category_vectors: WeakKeyDictionary[CategorySet, np.ndarray] = WeakKeyDictionary()


def similarities(text: str, categories: CategorySet, model_dir: str) -> list[float]:
    """Cosine similarity of the page text to each category's definition, in CSV order."""
    encoder = _encoder(str(resolve(model_dir)))
    if categories not in _category_vectors:
        _category_vectors[categories] = encoder.embed([f"passage: {_definition(c)}" for c in categories])
    page = encoder.embed([f"query: {text}"])[0]
    return (_category_vectors[categories] @ page).tolist()


def resolve(model_dir: str) -> Path:
    """A relative model directory is relative to the repository, wherever the tool is started from."""
    path = Path(model_dir)
    return path if path.is_absolute() else REPO_ROOT / path


def _definition(category) -> str:
    return f"{category.name}. {category.description} {'; '.join(category.positive_phrases)}"


class _Encoder:
    def __init__(self, model_dir: Path):
        import onnxruntime
        from tokenizers import Tokenizer

        if not (model_dir / "model_quantized.onnx").exists():
            raise FileNotFoundError(f"text encoder not found in {model_dir}; run: python docclassify.py fetch-model")
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(MAX_TOKENS)
        self._session = onnxruntime.InferenceSession(
            str(model_dir / "model_quantized.onnx"), providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}

    def embed(self, texts: list[str]) -> np.ndarray:
        """L2-normalised mean-pooled vectors, one row per text.

        One text at a time: padding texts to a common length shifts the quantised model's output slightly, which
        would make a category's vector depend on which other categories share its batch.
        """
        rows = []
        for text in texts:
            encoded = [self._tokenizer.encode(text)]
            ids = np.array([e.ids for e in encoded], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self._session.run(None, feed)[0]
            pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
            rows.append(pooled / np.linalg.norm(pooled, axis=1, keepdims=True))
        return np.vstack(rows)


@lru_cache(maxsize=2)
def _encoder(model_dir: str) -> _Encoder:
    return _Encoder(Path(model_dir))
