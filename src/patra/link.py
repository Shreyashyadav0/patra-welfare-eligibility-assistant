"""Scheme entity linking.

A light, deterministic linker: it matches scheme names and their common aliases,
including Devanagari forms, in the question. This matters twice. It raises retrieval
precision (a question that names PM-KISAN should not be answered from a PM-JAY
paragraph), and it is what makes a Hindi question retrievable at all when the vector
index is a lexical one.

The alias table is data, not code: extend it as schemes are added.
"""
from __future__ import annotations

import re

ALIASES: dict[str, list[str]] = {
    "pmkisan": ["pm-kisan", "pm kisan", "pmkisan", "kisan samman", "kisan",
                "पीएम-किसान", "पीएम किसान", "किसान सम्मान"],
    "pmjay": ["pm-jay", "pmjay", "ayushman", "ayushman bharat", "जय", "आयुष्मान", "आयुष्मान भारत"],
    "pmayg": ["pmay-g", "pmayg", "pmay", "gramin", "awas yojana", "आवास", "पीएमएवाई", "ग्रामीण आवास"],
    "pmuy": ["ujjwala", "pmuy", "lpg connection", "उज्ज्वला", "एलपीजी"],
    "nsp": ["nsp", "national scholarship", "scholarship", "छात्रवृत्ति", "एनएसपी", "स्कॉलरशिप"],
    "svanidhi": ["svanidhi", "pm svanidhi", "street vendor loan", "स्वनिधि", "फेरीवाला"],
}


def link_schemes(question: str) -> list[str]:
    """Return scheme ids named in the question, longest alias first."""
    q = question.lower()
    hits: list[tuple[int, str]] = []
    for scheme_id, aliases in ALIASES.items():
        for alias in aliases:
            if alias.lower() in q:
                hits.append((len(alias), scheme_id))
    hits.sort(reverse=True)
    seen: list[str] = []
    for _len, scheme_id in hits:
        if scheme_id not in seen:
            seen.append(scheme_id)
    return seen
