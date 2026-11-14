"""Deterministic eligibility engine.

This is the component the project claims. It is the only place in the system where
a value is compared with a threshold, and it never sees a language model.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .corpus import Criterion

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
INDETERMINATE = "indeterminate"
ABSTAINED = "abstained"

REASON_NO_EVIDENCE = "NO_EVIDENCE"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_MISSING_PROFILE = "MISSING_PROFILE"
REASON_MISSING_SOURCE = "MISSING_EVIDENCE_SOURCE"
REASON_CONFLICTING = "CONFLICTING_CLAUSES"


class EngineError(ValueError):
    pass


@dataclass
class PredicateResult:
    criterion_id: str
    field: str
    operator: str
    threshold: Any
    observed: Any
    outcome: str
    clause_text: str
    span: tuple[int, int]

    def as_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "field": self.field,
            "operator": self.operator,
            "threshold": self.threshold,
            "observed": self.observed,
            "outcome": self.outcome,
            "clause_text": self.clause_text,
            "span": list(self.span),
        }


@dataclass
class Verdict:
    verdict_type: str
    results: list[PredicateResult] = field(default_factory=list)
    reason_code: str | None = None

    @property
    def failed(self) -> list[PredicateResult]:
        return [r for r in self.results if r.outcome == FAIL]

    @property
    def unresolved(self) -> list[PredicateResult]:
        return [r for r in self.results if r.outcome == UNKNOWN]


def _normalise_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"yes", "y", "true", "1"}:
            return True
        if v in {"no", "n", "false", "0"}:
            return False
    return None


def _compare(observed: Any, operator: str, threshold: Any) -> bool:
    op = operator.strip().upper()
    if op in {"IS_TRUE", "IS_FALSE"}:
        b = _normalise_bool(observed)
        if b is None:
            raise EngineError(f"cannot read boolean from {observed!r}")
        return b if op == "IS_TRUE" else not b
    if op in {"==", "=", "EQ"}:
        return str(observed).lower() == str(threshold).lower() if isinstance(threshold, str) else observed == threshold
    if op in {"!=", "NE"}:
        return str(observed).lower() != str(threshold).lower() if isinstance(threshold, str) else observed != threshold
    if op in {"<", "<=", ">", ">="}:
        try:
            a = float(observed)
            b = float(threshold)
        except (TypeError, ValueError) as exc:
            raise EngineError(f"cannot compare {observed!r} with {threshold!r}") from exc
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    if op == "IN":
        values = threshold if isinstance(threshold, (list, tuple, set)) else [threshold]
        return str(observed) in {str(v) for v in values}
    if op == "BETWEEN":
        try:
            low, high = float(threshold[0]), float(threshold[1])
            value = float(observed)
        except (TypeError, ValueError, IndexError) as exc:
            raise EngineError(f"cannot compare {observed!r} with range {threshold!r}") from exc
        return low <= value <= high
    raise EngineError(f"unsupported operator {operator!r}")


def _interval(criterion: Criterion) -> tuple[float, float] | None:
    """The closed numeric interval a comparison admits, or None if it is not numeric.

    BETWEEN is handled before any float() cast on the threshold, because its threshold
    is a pair. A scalar threshold on BETWEEN is a data error and returns None rather
    than raising, so conflict detection can never crash on malformed criteria.
    """
    op = criterion.operator.strip().upper()
    if op == "BETWEEN":
        try:
            low, high = criterion.threshold
            return (float(low), float(high))
        except (TypeError, ValueError):
            return None
    try:
        t = float(criterion.threshold)
    except (TypeError, ValueError):
        return None
    if op == ">=":
        return (t, float("inf"))
    if op == ">":
        return (math.nextafter(t, math.inf), float("inf"))   # strict: excludes t
    if op == "<=":
        return (float("-inf"), t)
    if op == "<":
        return (float("-inf"), math.nextafter(t, -math.inf))
    if op in {"==", "=", "EQ"}:
        return (t, t)
    return None


def _has_conflict(criteria: list[Criterion]) -> bool:
    """True only when two clauses on the same field share no admissible value."""
    by_field: dict[str, list[Criterion]] = {}
    for c in criteria:
        by_field.setdefault(c.field, []).append(c)

    for field, group in by_field.items():
        # Categorical conflict: two different equality/IN targets that cannot both hold.
        sets = []
        for c in group:
            op = c.operator.strip().upper()
            if op in {"IN"}:
                vals = c.threshold if isinstance(c.threshold, (list, tuple, set)) else [c.threshold]
                sets.append({str(v) for v in vals})
            elif op in {"==", "=", "EQ"} and c.threshold is not None:
                sets.append({str(c.threshold)})
        if len(sets) > 1 and not set.intersection(*sets):
            return True

        # Numeric conflict: intersection of the admitted intervals is empty.
        low, high = float("-inf"), float("inf")
        seen = False
        for c in group:
            iv = _interval(c)
            if iv is None:
                continue
            seen = True
            low = max(low, iv[0])
            high = min(high, iv[1])
        if seen and low > high:
            return True
    return False


def evaluate(profile: dict[str, Any], criteria: list[Criterion]) -> Verdict:
    """Evaluate a profile against criteria. Any fail is decisive; unknown alone is not."""
    if not criteria:
        return Verdict(ABSTAINED, reason_code=REASON_NO_EVIDENCE)

    # A conflict exists only when two clauses on one field admit no common value.
    # An age band (>= 18 and <= 60) is a conjunction, not a contradiction.
    if _has_conflict(criteria):
        return Verdict(INDETERMINATE, reason_code=REASON_CONFLICTING)

    results: list[PredicateResult] = []
    for c in criteria:
        observed = profile.get(c.field)
        if observed is None or observed == "":
            outcome = UNKNOWN
        else:
            try:
                outcome = PASS if _compare(observed, c.operator, c.threshold) else FAIL
            except EngineError:
                outcome = UNKNOWN
        results.append(
            PredicateResult(
                criterion_id=c.criterion_id, field=c.field, operator=c.operator,
                threshold=c.threshold, observed=observed, outcome=outcome,
                clause_text=c.clause_text, span=(c.span_start, c.span_end),
            )
        )

    mandatory = [r for r, c in zip(results, criteria) if c.mandatory]
    if any(r.outcome == FAIL for r in mandatory):
        return Verdict(NOT_ELIGIBLE, results)
    if any(r.outcome == UNKNOWN for r in mandatory):
        return Verdict(INDETERMINATE, results, REASON_MISSING_PROFILE)
    return Verdict(ELIGIBLE, results)
