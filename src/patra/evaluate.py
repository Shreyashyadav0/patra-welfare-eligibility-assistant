"""Evaluation harness: retrieval, verdict, citation, abstention and cross-lingual metrics.

Design notes that matter for honesty:
* The gate is cross-fitted on scheme-disjoint folds, and every reported curve is
  out-of-fold. Fitting and scoring on the same items would inflate the result.
* Comparators (see docs) get the gold profile per item; the free-text number is
  reported separately, so the cost of parsing a question is visible rather than hidden.
* Targets from the synopsis are printed next to the measured value. A miss is a miss.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupKFold

from .engine import ABSTAINED
from .gate import AbstentionGate
from .pipeline import Pipeline

TARGETS = {
    "recall_at_5": 0.85,
    "verdict_accuracy": 0.80,
    "selective_accuracy": 0.85,
    "ece": 0.10,
    "excess_aurc": 0.12,
    "unnecessary_abstention": 0.15,
    "clvc_kappa": 0.80,
    "p95_latency_ms": 8000.0,
}


def load_bench(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _gold_chunk_hit(evidence, gold_clause: str) -> bool:
    if not gold_clause:
        return False
    needle = gold_clause.strip()
    return any(needle in e.chunk.text for e in evidence[:5])


def _ece(probs: list[float], labels: list[int], bins: int = 5) -> float:
    if not probs:
        return 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in itertools.pairwise(edges):
        idx = [i for i, p in enumerate(probs) if lo <= p < hi or (hi == 1.0 and p == 1.0)]
        if not idx:
            continue
        conf = float(np.mean([probs[i] for i in idx]))
        acc = float(np.mean([labels[i] for i in idx]))
        total += (len(idx) / len(probs)) * abs(acc - conf)
    return total


def _aurc(probs: list[float], correct: list[int]) -> float:
    if not probs:
        return 0.0
    order = np.argsort(-np.array(probs))
    risks, cum = [], 0
    for rank, i in enumerate(order, start=1):
        cum += 1 - correct[i]
        risks.append(cum / rank)
    return float(np.mean(risks))


def _oracle_aurc(correct: list[int]) -> float:
    if not correct:
        return 0.0
    order = sorted(range(len(correct)), key=lambda i: -correct[i])
    risks, cum = [], 0
    for rank, i in enumerate(order, start=1):
        cum += 1 - correct[i]
        risks.append(cum / rank)
    return float(np.mean(risks))


def _kappa(a: list[str], b: list[str]) -> float:
    if not a:
        return float("nan")
    labels = sorted(set(a) | set(b))
    n = len(a)
    obs = sum(1 for x, y in zip(a, b, strict=False) if x == y) / n
    exp = 0.0
    for label in labels:
        pa = sum(1 for x in a if x == label) / n
        pb = sum(1 for y in b if y == label) / n
        exp += pa * pb
    return (obs - exp) / (1 - exp) if exp < 1 else float("nan")


def run(pipeline: Pipeline, items: list[dict], n_folds: int = 5) -> dict:
    records = []
    for item in items:
        gold_profile = item["gold_profile"] or None
        ans = pipeline.answer(item["question"], profile=gold_profile, lang=item.get("lang", "en"))
        gold = item["gold_verdict"]
        correct = int(ans.verdict.verdict_type == gold)
        records.append(
            {
                "item_id": item["item_id"],
                "stratum": item["stratum"],
                "lang": item.get("lang", "en"),
                "answerable": item["answerable"],
                "gold": gold,
                "predicted": ans.verdict.verdict_type,
                "decision": ans.decision,
                "correct": correct,
                "features": ans.features,
                "recall_hit": _gold_chunk_hit(ans.evidence, item.get("gold_clause", "")),
                "recall_hit_retrieval_only": _gold_chunk_hit(
                    pipeline.retriever.retrieve(item["question"], top=5),
                    item.get("gold_clause", ""),
                ),
                "group": item["gold_scheme"],
                "latency_ms": ans.latency_ms,
                "reason_code": ans.reason_code,
            }
        )

    # ---- cross-fitted gate (scheme-disjoint folds) -------------------
    X = [AbstentionGate.featurise(r["features"]) for r in records]
    y = [r["correct"] for r in records]
    groups = [r["group"] for r in records]
    oof = np.zeros(len(records))
    folds = min(n_folds, len(set(groups)))
    if folds >= 2 and len(set(y)) > 1:
        for train_idx, test_idx in GroupKFold(n_splits=folds).split(X, y, groups):
            fold_gate = AbstentionGate().fit([X[i] for i in train_idx], [y[i] for i in train_idx])
            if fold_gate.model is None:
                oof[test_idx] = 0.5
            else:
                oof[test_idx] = fold_gate.model.predict_proba([X[i] for i in test_idx])[:, 1]
    else:
        oof[:] = 0.5

    gate = AbstentionGate()
    gate.model = None
    gate.threshold = gate._pick_threshold(oof, np.array(y))
    if len(set(y)) > 1:
        gate.fit(X, y)

    for rec, p in zip(records, oof, strict=False):
        rec["probability"] = float(p)
        if rec["predicted"] == ABSTAINED or p < gate.threshold:
            rec["final_decision"], rec["final"] = "abstain", "abstained"
        else:
            rec["final_decision"] = "answer"
            rec["final"] = rec["predicted"]

    # ---- metrics -----------------------------------------------------
    answerable = [r for r in records if r["answerable"]]
    answered = [r for r in answerable if r["final_decision"] == "answer"]
    unanswerable = [r for r in records if not r["answerable"]]

    coverage = len(answered) / len(answerable) if answerable else 0.0
    verdict_accuracy = (
        sum(1 for r in answered if r["predicted"] == r["gold"]) / len(answered) if answered else 0.0
    )
    selective_accuracy = (
        sum(1 for r in answered if r["predicted"] == r["gold"]) / len(answerable)
        if answerable
        else 0.0
    )
    recall = sum(1 for r in answerable if r["recall_hit"]) / len(answerable) if answerable else 0.0
    recall_ro = (
        sum(1 for r in answerable if r["recall_hit_retrieval_only"]) / len(answerable)
        if answerable
        else 0.0
    )
    unnecessary = (
        sum(1 for r in answerable if r["final_decision"] != "answer") / len(answerable)
        if answerable
        else 0.0
    )
    abstention_on_unanswerable = (
        sum(1 for r in unanswerable if r["final_decision"] == "abstain") / len(unanswerable)
        if unanswerable
        else 0.0
    )
    probs = [r["probability"] for r in records]
    correct = [r["correct"] for r in records]
    lat = sorted(r["latency_ms"] for r in records)
    p95 = lat[max(0, math.ceil(0.95 * len(lat)) - 1)] if lat else 0.0

    by_stratum = defaultdict(lambda: {"n": 0, "answered": 0, "correct": 0})
    for r in answerable:
        s = by_stratum[r["stratum"]]
        s["n"] += 1
        s["answered"] += int(r["final_decision"] == "answer")
        s["correct"] += int(r["predicted"] == r["gold"])

    # ---- cross-lingual consistency ----------------------------------
    pairs = defaultdict(dict)
    for r in records:
        base = r["item_id"].replace("HI", "")
        pairs[base][r["lang"]] = r["final"]
    en, hi = [], []
    for langs in pairs.values():
        if "en" in langs and "hi" in langs:
            en.append(langs["en"])
            hi.append(langs["hi"])
    clvc = _kappa(en, hi) if en else float("nan")
    clvc_raw = (
        (sum(1 for a, b in zip(en, hi, strict=False) if a == b) / len(en)) if en else float("nan")
    )

    # The honest denominators: every item counts, including the unanswerable ones.
    answered_all = [r for r in records if r["final_decision"] == "answer"]
    correct_all = sum(1 for r in answered_all if r["predicted"] == r["gold"])
    metrics = {
        "n_items": len(records),
        "accuracy_all_items": round(correct_all / len(records), 3) if records else 0.0,
        "coverage_all_items": round(len(answered_all) / len(records), 3) if records else 0.0,
        "selective_accuracy_all_items": round(correct_all / len(answered_all), 3)
        if answered_all
        else 0.0,
        "n_answerable": len(answerable),
        "coverage": round(coverage, 3),
        "verdict_accuracy": round(verdict_accuracy, 3),
        "selective_accuracy": round(selective_accuracy, 3),
        "recall_at_5": round(recall, 3),
        "retrieval_only_recall_at_5": round(recall_ro, 3),
        "unnecessary_abstention": round(unnecessary, 3),
        "abstention_on_unanswerable": round(abstention_on_unanswerable, 3),
        "ece": round(_ece(probs, correct), 3),
        "excess_aurc": round(max(0.0, _aurc(probs, correct) - _oracle_aurc(correct)), 3),
        "clvc_kappa": None if isinstance(clvc, float) and math.isnan(clvc) else round(clvc, 3),
        "clvc_raw_agreement": None
        if isinstance(clvc_raw, float) and math.isnan(clvc_raw)
        else round(clvc_raw, 3),
        "clvc_pairs": len(en),
        "gate_threshold": round(gate.threshold, 3),
        "p95_latency_ms": round(p95, 1),
        "by_stratum": {k: dict(v) for k, v in sorted(by_stratum.items())},
    }
    return {"metrics": metrics, "records": records}


def freetext_mode(pipeline: Pipeline, items: list[dict]) -> dict:
    """Same benchmark, but the profile is parsed from the question instead of supplied."""
    correct = 0
    total = 0
    asked = 0
    for item in items:
        if not item["answerable"]:
            continue
        ans = pipeline.answer(item["question"], profile=None, lang=item.get("lang", "en"))
        total += 1
        correct += int(ans.verdict.verdict_type == item["gold_verdict"])
        asked += int(ans.decision == "ask")
    return {
        "n": total,
        "verdict_accuracy_freetext": round(correct / total, 3) if total else 0.0,
        "asked_for_missing_field": asked,
    }


def format_table(result: dict) -> str:
    m = result["metrics"]
    rows = [
        ("recall_at_5", m["recall_at_5"]),
        ("verdict_accuracy", m["verdict_accuracy"]),
        ("selective_accuracy", m["selective_accuracy"]),
        ("ece", m["ece"]),
        ("excess_aurc", m["excess_aurc"]),
        ("unnecessary_abstention", m["unnecessary_abstention"]),
        ("clvc_kappa", m["clvc_kappa"]),
        ("p95_latency_ms", m["p95_latency_ms"]),
    ]
    lines = [f"{'metric':26s}{'measured':>10s}{'target':>10s}   verdict"]
    for name, value in rows:
        target = TARGETS.get(name)
        if value is None:
            lines.append(f"{name:26s}{'n/a':>10s}{target:>10.2f}   no pairs")
            continue
        ok = (
            (value >= target)
            if name in {"recall_at_5", "verdict_accuracy", "selective_accuracy", "clvc_kappa"}
            else (value <= target)
        )
        lines.append(f"{name:26s}{value:>10.2f}{target:>10.2f}   {'meets' if ok else 'MISSES'}")
    lines.append("")
    lines.append(
        f"coverage {m['coverage']:.2f}   n={m['n_items']} ({m['n_answerable']} answerable)   "
        f"gate threshold {m['gate_threshold']:.2f}"
    )
    lines.append(f"abstention on unanswerable items: {m['abstention_on_unanswerable']:.2f}")
    return "\n".join(lines)
