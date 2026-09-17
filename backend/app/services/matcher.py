from rapidfuzz.fuzz import token_set_ratio

from .attribute_templates import critical_keys
from .semantic import SemanticModel
from .standardizer import normalize_uom


def _attribute_score(
    a: dict, b: dict, critical: set[str]
) -> tuple[float, list[str], bool]:
    shared = set(a) & set(b)
    if not shared:
        return 0.0, [], False

    agreements = 0
    considered = 0
    explanation: list[str] = []
    critical_conflict = False

    for key in sorted(shared):
        left, right = a[key], b[key]
        considered += 1
        if left == right:
            agreements += 1
            explanation.append(f"same {key}: {left}")
        elif key in critical:
            critical_conflict = True
            explanation.append(f"conflict in {key}: {left} vs {right}")

    return (
        agreements / considered if considered else 0.0,
        explanation,
        critical_conflict,
    )


def compare_materials(
    left: dict, right: dict, semantic: SemanticModel | None = None
) -> tuple[float, list[str]]:
    left_norm = left["normalized_description"]
    right_norm = right["normalized_description"]

    text_score = token_set_ratio(left_norm, right_norm) / 100.0

    semantic_score = (
        semantic.similarity(left_norm, right_norm) if semantic is not None else 0.0
    )

    family = left.get("material_family") or right.get("material_family")
    attr_score, attr_explanation, critical_conflict = _attribute_score(
        left.get("extracted_attributes", {}),
        right.get("extracted_attributes", {}),
        critical_keys(family),
    )

    mfr_score = 0.0
    if left.get("manufacturer_part_no") and right.get("manufacturer_part_no"):
        if (
            left["manufacturer_part_no"].strip().lower()
            == right["manufacturer_part_no"].strip().lower()
        ):
            mfr_score = 1.0
            attr_explanation.append("same manufacturer part number")

    # Unit-of-measure harmonization: a genuine canonical mismatch is a soft
    # negative signal (likely different granularity of item).
    uom_penalty = 1.0
    left_uom = normalize_uom(left.get("uom"))
    right_uom = normalize_uom(right.get("uom"))
    if left_uom and right_uom:
        if left_uom == right_uom:
            attr_explanation.append(f"same unit of measure: {left_uom}")
        else:
            uom_penalty = 0.9
            attr_explanation.append(
                f"unit of measure differs: {left['uom']} vs {right['uom']}"
            )

    if semantic is not None:
        # Semantic agreement can only *lift* the lexical score toward 1.0 — it
        # closes part of the remaining gap, and never drags a match down.
        combined_text = text_score + (1.0 - text_score) * semantic_score * 0.6
        score = 0.60 * combined_text + 0.30 * attr_score + 0.10 * mfr_score
        text_line = (
            f"description similarity: {text_score:.0%} lexical, "
            f"{semantic_score:.0%} semantic → {combined_text:.0%} combined"
        )
    else:
        score = 0.60 * text_score + 0.30 * attr_score + 0.10 * mfr_score
        text_line = f"description similarity: {text_score:.0%}"

    score *= uom_penalty
    if critical_conflict:
        score *= 0.45

    explanation = [text_line] + attr_explanation
    if critical_conflict:
        explanation.append(
            "score reduced because a critical engineering attribute conflicts"
        )

    return round(score, 4), explanation
