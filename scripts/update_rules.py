"""Deterministic update decisions for previously confirmed constraints."""

from typing import Mapping, Optional

from scripts.validate_outputs import (
    _constraint_record_issues,
    _rule_records,
    validate_manifest_data,
)


CONSTRAINT_SEMANTIC_FIELDS = (
    "id",
    "domain",
    "type",
    "status",
    "scope",
    "text",
    "confidence",
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
    prior_manifest: Optional[Mapping[str, object]],
    current_rule: Mapping[str, object],
) -> bool:
    """Return whether an update needs a new explicit constraint decision."""
    if prior_manifest is None:
        return True
    try:
        validated_manifest = validate_manifest_data(dict(prior_manifest))
    except ValueError:
        return True
    rule_id = current_rule.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        return True
    previous_rule = _rule_records(validated_manifest).get(rule_id)
    if previous_rule is None or current_rule.get("type") != "constraint":
        return True
    if _constraint_record_issues(rule_id, "prior Manifest", validated_manifest):
        return True
    return any(
        _semantic_value(previous_rule.get(field))
        != _semantic_value(current_rule.get(field))
        for field in CONSTRAINT_SEMANTIC_FIELDS
    )
