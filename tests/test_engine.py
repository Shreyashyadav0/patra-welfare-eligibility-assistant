"""Truth table for the deterministic engine. This is the component the project claims."""
import pytest

from patra.corpus import Criterion
from patra.engine import (ABSTAINED, ELIGIBLE, INDETERMINATE, NOT_ELIGIBLE,
                          EngineError, _compare, evaluate)


def crit(field, op, thr, mandatory=True, cid="c1"):
    return Criterion(cid, "s", field, "other", op, thr, mandatory, f"{field} {op} {thr}", 0, 1, "d")


@pytest.mark.parametrize("observed,op,threshold,expected", [
    (150000, "<=", 200000, True),
    (200001, "<=", 200000, False),
    (200000, "<=", 200000, True),      # boundary is inclusive
    (200000, "<", 200000, False),
    (18, ">=", 18, True),
    (17, ">=", 18, False),
    ("BPL", "IN", ["BPL", "SC", "ST"], True),
    ("General", "IN", ["BPL", "SC", "ST"], False),
    (25, "BETWEEN", [18, 30], True),
    (31, "BETWEEN", [18, 30], False),
    ("no", "IS_FALSE", None, True),
    ("yes", "IS_FALSE", None, False),
    ("yes", "IS_TRUE", None, True),
])
def test_comparisons(observed, op, threshold, expected):
    assert _compare(observed, op, threshold) is expected


def test_missing_field_is_unknown_not_fail():
    verdict = evaluate({}, [crit("income_annual", "<=", 200000)])
    assert verdict.verdict_type == INDETERMINATE
    assert verdict.results[0].outcome == "unknown"
    assert verdict.reason_code == "MISSING_PROFILE"


def test_all_pass_is_eligible():
    verdict = evaluate({"income_annual": 100000, "age": 30},
                       [crit("income_annual", "<=", 200000), crit("age", ">=", 18, cid="c2")])
    assert verdict.verdict_type == ELIGIBLE


def test_one_fail_is_decisive_even_with_unknown():
    verdict = evaluate({"income_annual": 300000},
                       [crit("income_annual", "<=", 200000), crit("age", ">=", 18, cid="c2")])
    assert verdict.verdict_type == NOT_ELIGIBLE
    assert [r.field for r in verdict.failed] == ["income_annual"]


def test_optional_criterion_does_not_block():
    verdict = evaluate({"age": 30}, [crit("age", ">=", 18, mandatory=False)])
    assert verdict.verdict_type == ELIGIBLE


def test_age_band_is_a_conjunction_not_a_conflict():
    """>= 18 and <= 60 admit a common value: that is a band, not a contradiction."""
    criteria = [crit("age", ">=", 18), crit("age", "<=", 60, cid="c2")]
    assert evaluate({"age": 30}, criteria).verdict_type == ELIGIBLE


def test_disjoint_clauses_are_indeterminate():
    criteria = [crit("age", ">=", 60), crit("age", "<=", 18, cid="c2")]
    verdict = evaluate({"age": 30}, criteria)
    assert verdict.verdict_type == INDETERMINATE
    assert verdict.reason_code == "CONFLICTING_CLAUSES"


def test_strict_inequalities_that_exclude_everything_conflict():
    """age > 60 and age < 60 admit no common value, so that is a conflict."""
    criteria = [crit("age", ">", 60), crit("age", "<", 60, cid="c2")]
    verdict = evaluate({"age": 60}, criteria)
    assert verdict.verdict_type == INDETERMINATE
    assert verdict.reason_code == "CONFLICTING_CLAUSES"


def test_between_with_non_numeric_value_degrades_to_unknown():
    """A malformed profile must never raise out of the engine."""
    verdict = evaluate({"age": "eighteen"},
                       [Criterion("c1", "s", "age", "age", "BETWEEN", [18, 60], True, "x", 0, 1, "d")])
    assert verdict.verdict_type == INDETERMINATE
    assert verdict.results[0].outcome == "unknown"


def test_between_with_scalar_threshold_does_not_crash():
    """Bad data in the criteria table must degrade, not raise."""
    verdict = evaluate({"age": 30},
                       [Criterion("c1", "s", "age", "age", "BETWEEN", 30, True, "x", 0, 1, "d")])
    assert verdict.verdict_type in {INDETERMINATE, ELIGIBLE, NOT_ELIGIBLE}


def test_no_criteria_is_abstention():
    assert evaluate({"age": 30}, []).verdict_type == ABSTAINED


def test_unsupported_operator_raises():
    with pytest.raises(EngineError):
        _compare(1, "APPROXIMATELY", 2)


def test_type_mismatch_is_unknown_not_crash():
    verdict = evaluate({"income_annual": "a lot"}, [crit("income_annual", "<=", 200000)])
    assert verdict.verdict_type == INDETERMINATE
