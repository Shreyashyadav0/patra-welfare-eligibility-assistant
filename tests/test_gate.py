import numpy as np

from patra.gate import AbstentionGate


def test_featurise_accepts_dict_and_list():
    gate = AbstentionGate()
    n = len(gate.featurise({}))
    assert n == len(gate.featurise([0.0] * n))


def test_threshold_respects_min_coverage():
    probs = np.array([0.9] * 6 + [0.1] * 4)
    y = np.array([1] * 6 + [0] * 4)
    gate = AbstentionGate(min_coverage=0.3)
    threshold = gate._pick_threshold(probs, y)
    assert (probs >= threshold).mean() >= 0.3


def test_decisive_verdict_is_not_downgraded_to_ask():
    gate = AbstentionGate()
    gate.threshold = 0.0
    decision = gate.decide({"linked": 1.0}, "not_eligible", ["age"])
    assert decision.action == "answer"


def test_indeterminate_with_missing_field_asks():
    gate = AbstentionGate()
    gate.threshold = 0.0
    decision = gate.decide({"linked": 1.0}, "indeterminate", ["age"])
    assert decision.action == "ask"
