"""Lightweight semantic similarity for material descriptions.

Character n-gram TF-IDF cosine, built from the ingested corpus. It is offline
(no model download) and complements the token-based lexical score: it is robust
to re-ordered phrases, glued/!split tokens and abbreviations
("DGBB" vs "deep groove ball bearing", "6205-2Z" vs "6205 zz").
"""

import math
import re
from collections import Counter

_NGRAM = 3


def _grams(text: str) -> Counter:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return Counter()
    padded = f"  {text}  "
    return Counter(padded[i : i + _NGRAM] for i in range(len(padded) - _NGRAM + 1))


class SemanticModel:
    """An inverse-document-frequency table over the corpus' character n-grams."""

    def __init__(self, descriptions: list[str]):
        n_docs = max(1, len(descriptions))
        doc_freq: Counter = Counter()
        for desc in descriptions:
            doc_freq.update(set(_grams(desc)))
        self._idf = {
            gram: math.log((n_docs + 1) / (df + 1)) + 1.0
            for gram, df in doc_freq.items()
        }
        self._default_idf = math.log(n_docs + 1) + 1.0

    def _vector(self, text: str) -> dict[str, float]:
        vec: dict[str, float] = {}
        for gram, tf in _grams(text).items():
            weight = (1.0 + math.log(tf)) * self._idf.get(gram, self._default_idf)
            vec[gram] = weight
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {g: w / norm for g, w in vec.items()}

    def similarity(self, a: str, b: str) -> float:
        va, vb = self._vector(a), self._vector(b)
        if not va or not vb:
            return 0.0
        small, large = (va, vb) if len(va) < len(vb) else (vb, va)
        return max(0.0, min(1.0, sum(w * large.get(g, 0.0) for g, w in small.items())))
