"""Deterministic update decisions for explicitly confirmed constraints."""

import hashlib
from typing import Mapping, Optional

from scripts.manifest import confirmed_constraints, validate_manifest_data


CURRENT_TO_CONFIRMATION_FIELDS = {
    "scope": "scope",
    "reason": "reason",
    "exception_policy": "exception_policy",
    "verification": "verification",
}


def _normalized_text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _text_sha256(value: object) -> str:
    return hashlib.sha256(_normalized_text(value).encode("utf-8")).hexdigest()


def requires_constraint_confirmation(
    prior_manifest: Optional[Mapping[str, object]],
    current_rule: Mapping[str, object],
) -> bool:
    """Return whether a current strong constraint needs an explicit decision."""
    if prior_manifest is None or current_rule.get("type") != "constraint":
        return True
    rule_id = _normalized_text(current_rule.get("id"))
    if not rule_id:
        return True
    for field in ("scope", "text", "reason", "exception_policy", "verification"):
        if not _normalized_text(current_rule.get(field)):
            return True
    try:
        validated = validate_manifest_data(dict(prior_manifest))
    except ValueError:
        return True
    previous = confirmed_constraints(validated).get(rule_id)
    if previous is None:
        return True
    if previous.get("text_sha256") != _text_sha256(current_rule.get("text")):
        return True
    return any(
        _normalized_text(previous.get(record_field))
        != _normalized_text(current_rule.get(current_field))
        for current_field, record_field in CURRENT_TO_CONFIRMATION_FIELDS.items()
    )
