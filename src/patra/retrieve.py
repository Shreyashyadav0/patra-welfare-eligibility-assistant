"""Hybrid retrieval: BM25 + vector search, RRF fusion, then reranking.

The reranker here is a transparent lexical scorer, not a cross-encoder. It is
labelled as such because the synopsis claims a reranker ablation: the ablation is
only honest if the reader knows what is being ablated.
"""
from __future__ import annotations

from dataclasses import dataclass

from .corpus import Chunk, Corpus
from .index import BM25Index, VectorIndex, reciprocal_rank_fusion, tokenize


@dataclass
class Evidence:
    chunk: Chunk
    score_bm25: float
    score_vector: float
    score_fused: float
    score_rerank: float


class HybridRetriever:
    def __init__(self, corpus: Corpus, rrf_k: int = 60):
        self.corpus = corpus
        self.bm25 = BM25Index(corpus.chunks)
        self.vectors = VectorIndex(corpus.chunks)
        self.rrf_k = rrf_k

    def retrieve(self, query: str, candidates: int = 50, top: int = 10) -> list[Evidence]:
        bm25 = self.bm25.search(query, candidates)
        vec = self.vectors.search(query, candidates)
        fused = reciprocal_rank_fusion([bm25, vec], k=self.rrf_k, top=candidates)
        bm = dict(bm25)
        vc = dict(vec)
        evidence = []
        for chunk_id, fused_score in fused[:top]:
            chunk = self.corpus.chunk_by_id(chunk_id)
            evidence.append(
                Evidence(
                    chunk=chunk,
                    score_bm25=bm.get(chunk_id, 0.0),
                    score_vector=vc.get(chunk_id, 0.0),
                    score_fused=fused_score,
                    score_rerank=0.0,
                )
            )
        return self.rerank(query, evidence)

    def rerank(self, query: str, evidence: list[Evidence]) -> list[Evidence]:
        """Lexical overlap reranker, biased toward paragraphs that state a condition."""
        q = set(tokenize(query))
        for e in evidence:
            toks = set(tokenize(e.chunk.text))
            overlap = len(q & toks) / (len(q) or 1)
            condition_words = {"eligib", "must", "shall", "income", "age", "annual", "years"}
            boost = 0.15 if any(w in e.chunk.text.lower() for w in condition_words) else 0.0
            e.score_rerank = round(overlap + boost + 0.1 * e.score_fused, 6)
        return sorted(evidence, key=lambda e: -e.score_rerank)
