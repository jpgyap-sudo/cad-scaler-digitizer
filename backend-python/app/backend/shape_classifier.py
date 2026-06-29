"""
Deterministic furniture-type resolution from structured shape facts.

Generalizes the original one-off "round vs oval pedestal table" override
into a reusable framework: instead of trusting the vision model's
holistic category label (which has been observed giving 3 different
answers for the IDENTICAL test image across separate calls), ask it for
objective, low-level structural facts instead (support count/type, top
shape, arms, sectional segments) and run those facts through a plain
Python decision table here.

Facts are far more stable to extract than a final category label because
each one is a single, concrete, directly-observable question rather than
a synthesis of many cues into one judgment call. This doesn't eliminate
model variance entirely (the facts themselves can still occasionally be
misread), but it shrinks the surface area for drift to single yes/no/
small-enum answers instead of an open-ended label choice, and gives a
debuggable, inspectable decision path instead of a black box.

This is intentionally NOT exhaustive coverage of all 25+ furniture types -
only the ambiguous pairs that were actually observed flipping (table
shape family, chair arms) get a rule. Anything the rules don't have an
opinion on returns None, deferring to the existing AI-label / OpenCV
fallback chain unchanged.
"""

from typing import Optional


def classify_from_facts(facts: dict, ai_ftype: str = "") -> Optional[str]:
    """Return a deterministic furniture_type derived from `facts`, or None
    if the facts don't give a confident, mappable signal (caller should
    keep whatever type it already had).

    `facts` is the {support_count, support_type, top_shape, has_arms,
    is_sectional, category_hint} object the vision model is asked to
    report alongside (not instead of) its furniture_type guess.
    """
    if not isinstance(facts, dict) or not facts:
        return None

    support_count = facts.get("support_count")
    support_type = (facts.get("support_type") or "").lower().strip()
    top_shape = (facts.get("top_shape") or "").lower().strip()
    has_arms = facts.get("has_arms")
    category_hint = (facts.get("category_hint") or "").lower().strip()

    # Normalize support_count: model may report "many"/"4+"/an int/a numeric string
    count_num = None
    if isinstance(support_count, (int, float)):
        count_num = support_count
    elif isinstance(support_count, str):
        try:
            count_num = float(support_count)
        except ValueError:
            count_num = None  # e.g. "many"

    is_table = category_hint == "table" or _looks_like_table_type(ai_ftype)
    if is_table:
        single_column = (
            support_type in ("column", "pedestal_base", "panel")
            or (count_num is not None and count_num <= 1)
        )
        if single_column:
            if top_shape == "circle":
                return "round_pedestal_table"
            if top_shape == "oval":
                return "oval_pedestal_table"
            if top_shape in ("rectangle", "square"):
                # A single-support table with a rectangular/square top is
                # the asymmetric-pedestal family, not the legged
                # rectangular_table builder.
                return "asymmetric_pedestal_table"
            # top_shape unknown - not enough signal to pick a subtype,
            # but we DO know it's a single-pedestal table, not a 4-legged
            # one, so don't let it fall through to rectangular_table.
            return "asymmetric_pedestal_table" if support_type else None
        multi_leg = (
            support_type == "legs"
            or (count_num is not None and count_num >= 3)
        )
        if multi_leg:
            return "rectangular_table"

    if category_hint == "chair" or ai_ftype in ("chair", "dining_chair", "lounge_chair", "armchair_lounge"):
        if has_arms is True:
            return "armchair_lounge"
        if has_arms is False and ai_ftype not in ("dining_chair", "lounge_chair"):
            return "chair"

    # Sofas: no separate "sectional" furniture_type is currently reachable
    # via KNOWN_TYPES (a sofa.sectional.v1.json template graph exists but
    # isn't wired to a distinct dispatch type) - is_sectional is reported
    # for future use / debugging visibility but doesn't change the type
    # yet. Deliberately not faking a type change here.

    return None


def _looks_like_table_type(ftype: str) -> bool:
    ftype = (ftype or "").lower()
    return "table" in ftype or ftype in ("console_table", "office_desk")
