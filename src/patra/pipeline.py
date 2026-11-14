"""The end-to-end pipeline: retrieve, extract, evaluate, gate, compose."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .compose import compose
from .corpus import Corpus
from .engine import (ABSTAINED, ELIGIBLE, INDETERMINATE, NOT_ELIGIBLE, REASON_MISSING_SOURCE,
                     REASON_NO_EVIDENCE, Verdict, evaluate)
from .extract import Extraction, RuleProfileExtractor
from .gate import AbstentionGate
from .link import link_schemes
from .settings import UNLINKED_MIN_RERANK
from .retrieve import Evidence, HybridRetriever


@dataclass
class Answer:
    question: str
    scheme_id: str | None
    scheme_name: str
    verdict: Verdict
    decision: str
    reason_code: str | None
    probability: float | None
    features: dict[str, float]
    evidence: list[Evidence] = field(default_factory=list)
    rendered: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


class Pipeline:
    def __init__(self, corpus: Corpus, gate: AbstentionGate | None = None,
                 extractor: RuleProfileExtractor | None = None):
        self.corpus = corpus
        self.retriever = HybridRetriever(corpus)
        self.gate = gate or AbstentionGate()
        self.extractor = extractor or RuleProfileExtractor()

    # -- helpers -------------------------------------------------------
    def _features(self, evidence: list[Evidence], verdict: Verdict,
                  extraction: Extraction, linked: bool = False,
                  injected: int = 0) -> dict[str, float]:
        top = evidence[0] if evidence else None
        second = evidence[1] if len(evidence) > 1 else None
        total = max(len(verdict.results), 1)
        resolved = sum(1 for r in verdict.results if r.outcome != "unknown")
        return {
            "linked": 1.0 if linked else 0.0,
            "injected_share": injected / max(len(evidence) + injected, 1),
            "top1_bm25": top.score_bm25 if top else 0.0,
            "top1_vector": top.score_vector if top else 0.0,
            "score_margin": (top.score_fused - second.score_fused) if top and second else 0.0,
            "top1_rerank": top.score_rerank if top else 0.0,
            "resolved_share": resolved / total,
            "profile_coverage": extraction.coverage(),
        }

    def _schemes_in_play(self, evidence: list[Evidence]) -> list[str]:
        seen: list[str] = []
        for e in evidence[:3]:
            if e.chunk.scheme_id not in seen:
                seen.append(e.chunk.scheme_id)
        return seen

    # -- main entry point ---------------------------------------------
    def answer(self, question: str, profile: dict | None = None,
               lang: str = "en") -> Answer:
        started = time.perf_counter()
        extraction = self.extractor.extract(question) if profile is None else Extraction(
            profile=dict(profile), confidence={k: 1.0 for k in profile}
        )
        evidence = self.retriever.retrieve(question, top=8)
        linked = [s for s in link_schemes(question) if s in self.corpus.schemes]
        if linked:
            # Linked schemes take precedence, and within them the clauses the criteria
            # table actually evaluates come first: the system knows which sentences
            # decide, so it retrieves them to cite rather than hoping ranking finds them.
            deciding = {
                c.clause_text.strip()
                for sid in linked
                for c in self.corpus.schemes[sid].criteria
            }
            evidence.sort(key=lambda e: (
                e.chunk.scheme_id not in linked,
                e.chunk.text.strip() not in deciding,
                -e.score_rerank,
            ))
            # Clause injection: the criteria table names the sentences that decide, so
            # they are added to the evidence rather than left to ranking. Retrieval-only
            # recall is measured separately in evaluate.py, so this is visible, not hidden.
            present = {e.chunk.chunk_id for e in evidence}
            injected = []
            for sid in linked:
                for crit in self.corpus.schemes[sid].criteria:
                    for chunk in self.corpus.chunks_for_scheme(sid):
                        if chunk.text.strip() == crit.clause_text.strip() and chunk.chunk_id not in present:
                            injected.append(Evidence(chunk=chunk, score_bm25=0.0, score_vector=0.0,
                                                     score_fused=0.0, score_rerank=1.0))
                            present.add(chunk.chunk_id)
            evidence = injected + evidence
            schemes = linked + [s for s in self._schemes_in_play(evidence) if s not in linked]
        else:
            schemes = self._schemes_in_play(evidence)

        weak_unlinked = (
            not linked and (not evidence or evidence[0].score_rerank < UNLINKED_MIN_RERANK)
        )
        if not evidence or not schemes or weak_unlinked:
            verdict = Verdict(ABSTAINED, reason_code="NO_EVIDENCE")
            feats = self._features(evidence, verdict, extraction, linked=False)
            decision = self.gate.decide(feats, ABSTAINED, [])
            out = Answer(question, None, "the schemes held here", verdict,
                         "abstain", REASON_NO_EVIDENCE, decision.probability, feats, evidence)
            out.rendered = compose(out.scheme_name, verdict, "abstain", REASON_NO_EVIDENCE, lang)
            out.latency_ms = (time.perf_counter() - started) * 1000
            return out

        primary = schemes[0]
        criteria = self.corpus.schemes[primary].criteria
        # A scheme can be linked while none of its criteria carries a resolvable span,
        # in which case there is nothing to decide from: abstain and say why.
        if criteria and not any(c.span_end > c.span_start for c in criteria):
            verdict = Verdict(ABSTAINED, reason_code=REASON_MISSING_SOURCE)
            feats = self._features(evidence, verdict, extraction, linked=True)
            decision = self.gate.decide(feats, ABSTAINED, [])
            out = Answer(question, primary, self.corpus.schemes[primary].name, verdict,
                         "abstain", REASON_MISSING_SOURCE, decision.probability, feats, evidence)
            out.rendered = compose(out.scheme_name, verdict, "abstain", REASON_MISSING_SOURCE, lang)
            out.latency_ms = (time.perf_counter() - started) * 1000
            return out
        verdict = evaluate(extraction.profile, criteria)
        verdicts = {sid: evaluate(extraction.profile, self.corpus.schemes[sid].criteria)
                    for sid in schemes[:2]}

        if len(verdicts) > 1:
            types = {sid: v.verdict_type for sid, v in verdicts.items()}
            if ELIGIBLE in types.values():
                verdict = next(v for v in verdicts.values() if v.verdict_type == ELIGIBLE)
                primary = next(sid for sid, v in verdicts.items() if v.verdict_type == ELIGIBLE)
            elif all(v == NOT_ELIGIBLE for v in types.values()):
                verdict = next(iter(verdicts.values()))
            elif INDETERMINATE in types.values():
                verdict = next(v for v in verdicts.values() if v.verdict_type == INDETERMINATE)

        missing = sorted({r.field for r in verdict.results if r.outcome == "unknown"})
        injected = sum(1 for e in evidence if e.score_rerank == 1.0 and e.score_bm25 == 0.0)
        retrieval_only = [e for e in evidence if not (e.score_rerank == 1.0 and e.score_bm25 == 0.0)]
        feats = self._features(retrieval_only or evidence, verdict, extraction,
                               linked=bool(linked), injected=injected)
        decision = self.gate.decide(feats, verdict.verdict_type, missing)

        scheme = self.corpus.schemes[primary]
        out = Answer(question, primary, scheme.name, verdict, decision.action,
                     decision.reason_code, decision.probability, feats, evidence)
        out.rendered = compose(scheme.name, verdict, decision.action, decision.reason_code,
                               lang, decision.probability, scheme.official_url, scheme.source_note)
        out.latency_ms = (time.perf_counter() - started) * 1000
        return out
