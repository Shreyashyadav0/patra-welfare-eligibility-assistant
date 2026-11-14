"""Answer composition.

The composer renders facts the engine computed. It may not introduce a number: every
number in the answer comes from the verdict object, and every criterion carries the
clause it came from.
"""

from __future__ import annotations

from .engine import Verdict
from .settings import DISCLAIMER

TEMPLATES = {
    "eligible": "You appear to be eligible for {scheme}.",
    "not_eligible": "You do not appear to be eligible for {scheme}.",
    "indeterminate": "Your eligibility for {scheme} cannot be decided from the information given.",
    "abstained": "The documents held here do not settle whether you are eligible for {scheme}.",
}

TEMPLATES_HI = {
    "eligible": "आप {scheme} के लिए पात्र प्रतीत होते हैं।",
    "not_eligible": "आप {scheme} के लिए पात्र प्रतीत नहीं होते।",
    "indeterminate": "दी गई जानकारी से {scheme} के लिए आपकी पात्रता तय नहीं हो सकती।",
    "abstained": "उपलब्ध दस्तावेज़ों से यह तय नहीं होता कि आप {scheme} के लिए पात्र हैं या नहीं।",
}

REASONS = {
    "NO_EVIDENCE": "No clause in the held documents addresses this question.",
    "LOW_CONFIDENCE": "The evidence found is not strong enough to support a verdict.",
    "MISSING_PROFILE": "A required detail is missing, so the condition cannot be checked.",
    "MISSING_EVIDENCE_SOURCE": "The deciding register is restricted or not held.",
    "CONFLICTING_CLAUSES": "Two clauses impose incompatible conditions.",
}


def compose(
    scheme_name: str,
    verdict: Verdict,
    decision: str,
    reason: str | None,
    lang: str = "en",
    probability: float | None = None,
    source_url: str = "",
    source_note: str = "",
) -> dict:
    templates = TEMPLATES_HI if lang == "hi" else TEMPLATES
    if decision == "answer":
        head = templates[verdict.verdict_type].format(scheme=scheme_name)
    elif decision == "ask":
        head = templates["indeterminate"].format(scheme=scheme_name)
    else:
        head = templates["abstained"].format(scheme=scheme_name)

    rows = [r.as_dict() for r in verdict.results]
    citations = [
        {
            "criterion_id": r.criterion_id,
            "clause": r.clause_text,
            "span": list(r.span),
            "source_url": source_url,
        }
        for r in verdict.results
    ]
    failed = [r.field for r in verdict.results if r.outcome == "fail"]
    unknown = [r.field for r in verdict.results if r.outcome == "unknown"]

    return {
        "answer": head,
        "decision": decision,
        "verdict_type": verdict.verdict_type,
        "reason_code": reason,
        "reason_text": REASONS.get(reason or "", ""),
        "probability": round(probability, 3) if probability is not None else None,
        "failed_fields": failed,
        "unknown_fields": unknown,
        "criteria": rows,
        "citations": citations,
        "source_url": source_url,
        "source_note": source_note,
        "disclaimer": DISCLAIMER,
    }
