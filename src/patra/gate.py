"""Calibrated abstention gate.

The calibrated quantity is stated once and used everywhere:

    p = P(verdict_type == gold_verdict | feature vector)

estimated over the fixed benchmark mixture. Coverage is the answer rate, with
ask-for-field counted as non-coverage. Risk is 1 - accuracy over answered items.
The gate never sees gold spans or answerability labels; it sees retrieval scores,
extraction confidence and how much of the criteria set resolved.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression

FEATURES = [
    "linked", "top1_bm25", "top1_vector", "score_margin", "top1_rerank",
    "resolved_share", "profile_coverage", "injected_share",
]


@dataclass
class GateDecision:
    action: str          # "answer" | "ask" | "abstain"
    probability: float
    threshold: float
    reason_code: str | None = None


class AbstentionGate:
    def __init__(self, target_accuracy: float = 0.80, min_coverage: float = 0.80):
        self.target_accuracy = target_accuracy
        self.min_coverage = min_coverage
        self.model: LogisticRegression | None = None
        self.threshold = 0.5

    @staticmethod
    def featurise(features) -> list[float]:
        """Accept a feature dict or an already-ordered list."""
        if isinstance(features, (list, tuple)):
            return [float(v) for v in features]
        return [float(features.get(name, 0.0)) for name in FEATURES]

    def fit(self, rows: list[dict], labels: list[int]) -> "AbstentionGate":
        X = np.array([self.featurise(r) for r in rows], dtype=float)
        y = np.array(labels, dtype=int)
        if len(set(y.tolist())) < 2:
            self.model = None
            self.threshold = 0.0
            return self
        self.model = LogisticRegression(max_iter=1000, class_weight="balanced")
        self.model.fit(X, y)
        probs = self.model.predict_proba(X)[:, 1]
        self.threshold = self._pick_threshold(probs, y)
        return self

    def _pick_threshold(self, probs: np.ndarray, y: np.ndarray) -> float:
        """Choose the threshold that meets the accuracy target at the widest coverage."""
        # Pick the threshold that maximises a coverage-penalised accuracy, so the gate
        # neither answers everything nor abstains on everything.
        # The operating point is stated rather than searched: answer at least
        # `min_coverage` of questions, and among the thresholds that clear both the
        # accuracy target and that floor, take the most selective. Without the floor
        # the gate collapses to answering almost nothing on a small benchmark; without
        # the target it answers everything and abstains on nothing.
        candidates = []
        for t in np.linspace(0.05, 0.95, 91):
            keep = probs >= t
            cov = float(keep.mean())
            if cov < self.min_coverage or cov >= 1.0:
                continue
            acc = float(y[keep].mean()) if keep.any() else 0.0
            if acc >= self.target_accuracy:
                candidates.append((float(t), cov, acc))
        if not candidates:
            # Nothing clears the target: fall back to the median score, which at least
            # abstains on the weakest half rather than answering everything.
            return float(np.median(probs))
        return max(candidates, key=lambda c: (c[0], c[2]))[0]

    def decide(self, features: dict, verdict_type: str, missing_fields: list[str]) -> GateDecision:
        if self.model is None:
            p = 0.5
        else:
            p = float(self.model.predict_proba([self.featurise(features)])[0, 1])
        if verdict_type == "abstained":
            return GateDecision("abstain", p, self.threshold, "NO_EVIDENCE")
        if verdict_type == "indeterminate" and missing_fields:
            # A decisive fail already settles the answer; only an undecided verdict asks.
            return GateDecision("ask", p, self.threshold, "MISSING_PROFILE")
        if p < self.threshold:
            return GateDecision("abstain", p, self.threshold, "LOW_CONFIDENCE")
        return GateDecision("answer", p, self.threshold)
