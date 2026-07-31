"""Single authoritative vocabulary for canonical rule sections and directives."""

import re
from typing import Dict, List, Tuple


LANGUAGE_HEADINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "scope": "Scope",
        "facts": "Confirmed facts",
        "constraints": "Confirmed constraints",
        "rules": "Execution rules",
        "verification": "Verification",
        "related": "Related rules",
    },
    "zh-CN": {
        "scope": "适用范围",
        "facts": "已确认事实",
        "constraints": "已确认的强约束",
        "rules": "执行规则",
        "verification": "验证方式",
        "related": "相关规则",
    },
}
SECTION_KEY_BY_HEADING = {
    heading: key
    for mapping in LANGUAGE_HEADINGS.values()
    for key, heading in mapping.items()
}
MANDATORY_DIRECTIVE_TOKENS = ("MUST", "NEVER", "必须", "禁止")
STRONG_CONSTRAINT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:MUST|NEVER)(?![A-Za-z0-9_])|必须|禁止",
    re.IGNORECASE,
)
CONSTRAINT_MARKER_PATTERN = re.compile(
    r"^<!-- rule-id: ([a-z0-9][a-z0-9._-]*) -->$"
)


def normalize_rule_text(value: object) -> str:
    """Trim and collapse Unicode whitespace without changing case or punctuation."""
    return " ".join(str(value).split())


def parse_confirmed_constraint_block(value: str) -> List[Tuple[str, str]]:
    """Parse strict marker/list-item pairs used by confirmed constraints."""
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines or len(lines) % 2:
        raise ValueError("confirmed constraint block requires marker/item pairs")
    result = []
    seen = set()
    for index in range(0, len(lines), 2):
        marker = CONSTRAINT_MARKER_PATTERN.fullmatch(lines[index])
        body = lines[index + 1]
        if marker is None or not body.startswith("- "):
            raise ValueError("confirmed constraint requires one marker and list item")
        text = body[2:].strip()
        if not text or STRONG_CONSTRAINT_PATTERN.search(text) is None:
            raise ValueError("confirmed constraint item must contain a strong directive")
        rule_id = marker.group(1)
        if rule_id in seen:
            raise ValueError("confirmed constraint rule IDs must be unique")
        seen.add(rule_id)
        result.append((rule_id, text))
    return result
