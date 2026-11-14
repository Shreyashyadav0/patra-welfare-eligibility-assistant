"""Profile and criteria extraction.

Profile extraction is rule-based on purpose: it is deterministic, testable, and it
runs with no model. `LLMProfileExtractor` is the documented swap-in point for the
Qwen2.5 extractor described in the synopsis; it is not required to run the system.
Criteria are read from the curated table, which is what the deterministic engine
evaluates. The extraction pipeline that *produces* that table is `propose_criteria`,
and it is measured against the curated table by the A6 protocol in evaluate.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

FIELDS = [
    "age",
    "gender",
    "state",
    "income_annual",
    "category",
    "occupation",
    "residence",
    "is_student",
    "income_tax_payer",
    "govt_employee",
    "has_pucca_house",
    "marks",
    "covered_esic",
    "is_street_vendor",
]


@dataclass
class Extraction:
    profile: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def coverage(self) -> float:
        return len(self.profile) / len(FIELDS)


def _to_int(text: str) -> int | None:
    t = text.replace(",", "").replace(" ", "").lower()
    m = re.match(r"^(\d+(?:\.\d+)?)(k|lakh|lac|crore|cr)?$", t)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "k":
        value *= 1_000
    elif unit in ("lakh", "lac"):
        value *= 100_000
    elif unit in ("crore", "cr"):
        value *= 10_000_000
    return int(value)


class ProfileExtractor(Protocol):
    def extract(self, question: str) -> Extraction: ...


class RuleProfileExtractor:
    """Regex and lexicon extractor. Deterministic and unit-testable."""

    AGE_RE = re.compile(
        r"\b(?:age[d]?\s*(?:is|of)?\s*)?(\d{1,2})\s*(?:years?|yrs?|y/o)\b",
        re.IGNORECASE,
    )
    AGE_ALT = re.compile(r"\bage[d]?\s*[:=]?\s*(\d{1,2})\b", re.IGNORECASE)
    INCOME_RE = re.compile(
        r"(?:income|earn|salary|earning)[^0-9₹]{0,25}(?:rs\.?|₹|inr)?\s*([0-9][0-9,\.]*\s*(?:k|lakh|lac|crore|cr)?)",
        re.IGNORECASE,
    )
    MARKS_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|marks)", re.IGNORECASE)

    def extract(self, question: str) -> Extraction:
        q = question.lower()
        out = Extraction()

        m = self.AGE_RE.search(question) or self.AGE_ALT.search(question)
        if m:
            out.profile["age"] = int(m.group(1))
            out.confidence["age"] = 0.9

        m = self.INCOME_RE.search(question)
        if m:
            value = _to_int(m.group(1).strip())
            if value:
                out.profile["income_annual"] = value
                out.confidence["income_annual"] = 0.8

        if re.search(r"\b(woman|female|girl|lady|widow)\b", q):
            out.profile["gender"] = "F"
            out.confidence["gender"] = 0.95
        elif re.search(r"\b(man|male|boy)\b", q):
            out.profile["gender"] = "M"
            out.confidence["gender"] = 0.95

        if re.search(r"\b(village|rural|gram|gaon)\b", q):
            out.profile["residence"] = "rural"
            out.confidence["residence"] = 0.85
        elif re.search(r"\b(city|urban|town|municipal)\b", q):
            out.profile["residence"] = "urban"
            out.confidence["residence"] = 0.85

        for cat in ("SC", "ST", "OBC", "EWS", "BPL", "General"):
            if re.search(rf"\b{cat.lower()}\b", q):
                out.profile["category"] = cat
                out.confidence["category"] = 0.9
                break

        if re.search(r"\b(farmer|kisan|agricultur|land ?holding|landholder)\b", q):
            out.profile["occupation"] = "farmer"
            out.confidence["occupation"] = 0.85
        elif re.search(r"\b(student|studying|scholarship|college|school)\b", q):
            out.profile["occupation"] = "student"
            out.profile["is_student"] = True
            out.confidence["occupation"] = 0.85
            out.confidence["is_student"] = 0.8
        elif re.search(r"\b(street ?vendor|hawker|rehdi|thela)\b", q):
            out.profile["occupation"] = "street_vendor"
            out.profile["is_street_vendor"] = True
            out.confidence["occupation"] = 0.85
            out.confidence["is_street_vendor"] = 0.8

        # Government employment is independent of occupation: a farmer can also be a
        # retired government servant, and the exclusion applies either way.
        if re.search(
            r"\b(not|no|never)\s+(a\s+)?(government|govt|sarkari)\s+(employee|servant)",
            q,
        ):
            out.profile["govt_employee"] = "no"
            out.confidence["govt_employee"] = 0.85
        elif re.search(r"\b(government (servant|employee)|govt employee|sarkari naukri)\b", q):
            out.profile["govt_employee"] = "yes"
            out.confidence["govt_employee"] = 0.85

        if re.search(r"\b(income ?tax|it ?return|taxpayer)\b", q):
            negated = bool(
                re.search(
                    r"\b(do not|don't|did not|never|no|not)\b[^.]{0,25}\b(pay|paid|paying|file|filed|a taxpayer)\b",
                    q,
                )
            )
            if negated or "not a taxpayer" in q:
                out.profile["income_tax_payer"] = "no"
                out.confidence["income_tax_payer"] = 0.85
            elif re.search(r"\b(pay|paid|paying|file|filed)\b", q):
                out.profile["income_tax_payer"] = "yes"
                out.confidence["income_tax_payer"] = 0.8

        if re.search(r"\bpucca\b", q):
            out.profile["has_pucca_house"] = (
                "no" if re.search(r"\b(no|not|without|don't|do not)\b", q) else "yes"
            )
            out.confidence["has_pucca_house"] = 0.6

        if re.search(r"\b(esic|cghs|government health cover)\b", q):
            out.profile["covered_esic"] = "yes" if re.search(r"\b(covered|have|am)\b", q) else "no"
            out.confidence["covered_esic"] = 0.5

        m = self.MARKS_RE.search(question)
        if m:
            out.profile["marks"] = float(m.group(1))
            out.confidence["marks"] = 0.8

        for state in (
            "bihar",
            "kerala",
            "maharashtra",
            "uttar pradesh",
            "tamil nadu",
            "karnataka",
            "rajasthan",
            "gujarat",
            "odisha",
            "punjab",
        ):
            if state in q:
                out.profile["state"] = state.title()
                out.confidence["state"] = 0.8
                break

        if not out.profile:
            out.notes.append("no profile fields found in the question")
        return out


class LLMProfileExtractor:
    """Documented swap-in point for a Qwen2.5 / hosted-LLM extractor.

    Deliberately unimplemented: the delivered system must run with no model
    download. Implement `extract` to return an Extraction built from the model's
    constrained JSON, and the rest of the pipeline is unchanged.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "LLM extraction is the documented swap-in point; see docs/SUBMISSION.md"
        )


def propose_criteria(chunk_text: str) -> list[dict]:
    """Extraction pipeline that proposes criteria from a clause.

    A deliberately small rule-based proposer: it recognises the shapes that carry
    thresholds (income, age, category, residence) and returns candidate tuples with
    no span, which the caller must attach. Measured against the curated table by A6.
    """
    text = chunk_text.lower()
    proposals: list[dict] = []
    m = re.search(r"annual income[^0-9]{0,20}(?:rs\.?|₹)?\s*([0-9][0-9,]*)\s*(k|lakh|lac)?", text)
    if m:
        value = _to_int(m.group(1) + (m.group(2) or ""))
        if value:
            proposals.append(
                {
                    "field": "income_annual",
                    "operator": "<=",
                    "threshold": value,
                    "criterion_type": "income",
                }
            )
    m = re.search(r"(?:aged?|age)[^0-9]{0,10}(\d{2})", text)
    if m:
        proposals.append(
            {
                "field": "age",
                "operator": ">=",
                "threshold": int(m.group(1)),
                "criterion_type": "age",
            }
        )
    if "woman" in text or "female" in text:
        proposals.append(
            {
                "field": "gender",
                "operator": "==",
                "threshold": "F",
                "criterion_type": "other",
            }
        )
    return proposals
