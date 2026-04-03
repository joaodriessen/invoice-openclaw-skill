"""
BTW rules for Dutch ZZP musician invoices.

Sources: Rijksoverheid / Belastingdienst
- Cultural performances (optredens, concerten, repetities): 9% verlaagd tarief
- Music education to individuals under 21: vrijgesteld (0%)
- Music education to individuals 21 and older: 21% standaardtarief
"""

from __future__ import annotations

# Canonical BTW rates
RATE_9 = 0.09
RATE_21 = 0.21
RATE_0 = 0.00

# Map of keyword → rate
_RULES: dict[str, float] = {
    # Performances — 9%
    "optreden":     RATE_9,
    "optreden9":    RATE_9,
    "concert":      RATE_9,
    "repetitie":    RATE_9,
    "uitvoering":   RATE_9,
    "performance":  RATE_9,
    "spelen":       RATE_9,

    # Education under 21 — vrijgesteld (0%)
    "les":          RATE_0,
    "les0":         RATE_0,
    "muziekles":    RATE_0,
    "onderwijs":    RATE_0,
    "lesgeven":     RATE_0,
    "cursus":       RATE_0,
    "workshop":     RATE_0,
    "vrijgesteld":  RATE_0,

    # Education 21 and older — 21%
    "les21":        RATE_21,
    "les_21":       RATE_21,
    "les_21plus":   RATE_21,
    "muziekles21":  RATE_21,
    "cursus21":     RATE_21,
    "workshop21":   RATE_21,
    "21plus":       RATE_21,
}

# Human-readable labels per rate
BTW_LABEL: dict[float, str] = {
    RATE_0:  "BTW vrijgesteld",
    RATE_9:  "BTW 9%",
    RATE_21: "BTW 21%",
}

# Explanation per rate (for validation output)
BTW_DESCRIPTION: dict[float, str] = {
    RATE_0:  "Vrijgesteld — muziekles aan particulieren onder 21 jaar",
    RATE_9:  "Verlaagd tarief — optredens, concerten, repetities",
    RATE_21: "Standaardtarief — muziekles aan particulieren van 21 jaar en ouder",
}

VALID_TYPES = sorted(_RULES.keys())


def resolve_btw(btw_type: str) -> float:
    """
    Resolve a BTW type string to a rate (0.0, 0.09, or 0.21).

    Accepts keywords (see VALID_TYPES) or numeric strings ("0", "9", "21",
    "0.09", "0.21", "9%", "21%").

    Raises ValueError if the type is not recognised.
    """
    key = btw_type.lower().strip().rstrip("%")

    # Direct keyword lookup
    if key in _RULES:
        return _RULES[key]

    # Numeric input: accept 0, 9, 21, 0.09, 0.21
    try:
        numeric = float(key)
        # Treat as percentage if > 1
        if numeric > 1:
            numeric = numeric / 100
        rate = round(numeric, 4)
        if rate in (RATE_0, RATE_9, RATE_21):
            return rate
    except ValueError:
        pass

    raise ValueError(
        f"Onbekend BTW-type: '{btw_type}'.\n"
        f"Geldige types: {', '.join(VALID_TYPES)}\n"
        f"Of gebruik een percentage: 0, 9, 21 (of 0%, 9%, 21%)"
    )


def label(rate: float) -> str:
    """Human-readable BTW label for a rate."""
    return BTW_LABEL.get(rate, f"BTW {int(rate * 100)}%")


def description(rate: float) -> str:
    """Full description of why this rate applies."""
    return BTW_DESCRIPTION.get(rate, "")
