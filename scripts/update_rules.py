"""Deterministic update decisions for previously confirmed constraints."""

from typing import Mapping, Optional


CONSTRAINT_SEMANTIC_FIELDS = (
    "id",
    "type",
    "status",
    "scope",
    "text",
    "reason",
    "exception_policy",
    "verification",
    "confirmation_id",
)


def _semantic_value(value: object) -> object:
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def requires_constraint_confirmation(
    previous_rule: Optional[Mapping[str, object]],
    current_rule: Mapping[str, object],
    *,
    already_canonical: bool,
) -> bool:
    """Return whether an update needs a new explicit constraint decision."""
    if not already_canonical or previous_rule is None:
        return True
    if (
        previous_rule.get("type") != "constraint"
        or previous_rule.get("status") != "confirmed"
        or current_rule.get("type") != "constraint"
    ):
        return True
    return any(
        _semantic_value(previous_rule.get(field))
        != _semantic_value(current_rule.get(field))
        for field in CONSTRAINT_SEMANTIC_FIELDS
    )
