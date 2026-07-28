"""Single authoritative vocabulary for canonical rule sections and directives."""

import re
from typing import Dict


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


def normalize_rule_text(value: object) -> str:
    """Trim and collapse Unicode whitespace without changing case or punctuation."""
    return " ".join(str(value).split())
