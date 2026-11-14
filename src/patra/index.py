"""Lexical and vector indexes, plus reciprocal rank fusion.

Honest note on the "dense" side: a TF-IDF cosine index is used so the system runs
with no model download. It is a lexical-vector fallback, not a neural embedding
model. `VectorIndex` exposes the same interface a BGE-M3 index would, so swapping
in a real embedder is a one-class change (see docs/SUBMISSION.md).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .corpus import Chunk

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[tuple[str, float]]: ...


class BM25Index:
    """Okapi BM25 over chunks."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunk_ids = [c.chunk_id for c in chunks]
        self.docs = [tokenize(c.text) for c in chunks]
        self.k1, self.b = k1, b
        self.doc_len = [len(d) for d in self.docs]
        self.avg_len = (sum(self.doc_len) / len(self.docs)) if self.docs else 0.0
        self.tf = [Counter(d) for d in self.docs]
        df: Counter = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        q = tokenize(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            dl = self.doc_len[i] or 1
            for t in q:
                if t not in tf:
                    continue
                idf = self.idf.get(t, 0.0)
                freq = tf[t]
                s += idf * (freq * (self.k1 + 1)) / (
                    freq + self.k1 * (1 - self.b + self.b * dl / (self.avg_len or 1))
                )
            if s > 0:
                scores.append((self.chunk_ids[i], s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]


class VectorIndex:
    """TF-IDF cosine index standing in for a neural embedder."""

    def __init__(self, chunks: list[Chunk]):
        self.chunk_ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks] or ["empty"]
        self.vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(texts)

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        qv = self.vectorizer.transform([query])
        sims = (self.matrix @ qv.T).toarray().ravel()
        order = np.argsort(-sims)
        out = []
        for i in order[:k]:
            if sims[i] > 0:
                out.append((self.chunk_ids[int(i)], float(sims[i])))
        return out


def reciprocal_rank_fusion(
    rankings: Iterable[list[tuple[str, float]]], k: int = 60, top: int = 20
) -> list[tuple[str, float]]:
    """RRF: score = sum over lists of 1 / (k + rank). Rank-based, so scales never clash."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (chunk_id, _score) in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda x: -x[1])
    return ordered[:top]
