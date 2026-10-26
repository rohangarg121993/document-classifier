"""Text normalisation shared by page text and keywords, so both sides compare equally."""

import re
import unicodedata

_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, spell out umlauts and ß, strip other accents, reduce to words separated by single spaces."""
    # NFC first: some PDFs store "ü" as "u" + combining diaeresis, which the umlaut mapping would miss.
    text = unicodedata.normalize("NFC", text).lower().translate(_GERMAN)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _NON_ALNUM.sub(" ", text).strip()
