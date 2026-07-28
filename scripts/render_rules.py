"""Render canonical rule templates in one selected output language."""

import re
from pathlib import Path
from typing import Mapping


HEADING_TRANSLATIONS = {
    "en": {
        "SCOPE_HEADING": "Scope",
        "FACTS_HEADING": "Confirmed facts",
        "CONSTRAINTS_HEADING": "Confirmed constraints",
        "RULES_HEADING": "Execution rules",
        "VERIFICATION_HEADING": "Verification",
        "RELATED_HEADING": "Related rules",
    },
    "zh-CN": {
        "SCOPE_HEADING": "适用范围",
        "FACTS_HEADING": "已确认事实",
        "CONSTRAINTS_HEADING": "已确认的强约束",
        "RULES_HEADING": "执行规则",
        "VERIFICATION_HEADING": "验证方式",
        "RELATED_HEADING": "相关规则",
    },
}
DOMAIN_TITLES = {
    "en": {
        "project": "project",
        "architecture": "architecture",
        "coding-style": "coding style",
        "frontend": "frontend",
        "backend": "backend",
        "api": "API",
        "database": "database",
        "testing": "testing",
        "security": "security",
        "restrictions": "restrictions",
    },
    "zh-CN": {
        "project": "项目",
        "architecture": "架构",
        "coding-style": "编码风格",
        "frontend": "前端",
        "backend": "后端",
        "api": "接口",
        "database": "数据库",
        "testing": "测试",
        "security": "安全",
        "restrictions": "强约束",
    },
}
REQUIRED_VALUES = (
    "PROJECT_NAME",
    "SCOPE",
    "CONFIRMED_FACTS",
    "EXECUTION_RULES",
    "VERIFICATION",
    "RELATED_RULES",
)
TEMPLATE_METADATA_PATTERN = re.compile(
    r"\A<!--\s*TEMPLATE METADATA.*?-->\s*", re.DOTALL
)
CONDITIONAL_CONSTRAINT_PATTERN = re.compile(
    r"<!--\s*CONDITIONAL SECTION:.*?\n"
    r"(?P<body>##\s+\{\{CONSTRAINTS_HEADING\}\}\s*\n"
    r"\{\{CONFIRMED_CONSTRAINTS\}\}\s*\n)-->\s*",
    re.DOTALL,
)
UNRESOLVED_PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def render_rule_template(
    template_path: Path,
    language: str,
    values: Mapping[str, object],
) -> str:
    """Render one canonical rule file with language-specific headings."""
    headings = HEADING_TRANSLATIONS.get(language)
    domain_titles = DOMAIN_TITLES.get(language)
    if headings is None or domain_titles is None:
        raise ValueError("language must be en or zh-CN")
    domain = template_path.stem
    if domain not in domain_titles:
        raise ValueError("template name is not a supported canonical domain")

    replacements = {}
    for field in REQUIRED_VALUES:
        value = values.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Rule template requires a non-empty {}".format(field))
        replacements[field] = value.strip()
    constraints = values.get("CONFIRMED_CONSTRAINTS", "")
    if not isinstance(constraints, str):
        raise ValueError("CONFIRMED_CONSTRAINTS must be a string")
    replacements["CONFIRMED_CONSTRAINTS"] = constraints.strip()
    replacements.update(headings)
    replacements["DOMAIN_TITLE"] = domain_titles[domain]

    content = template_path.read_text(encoding="utf-8")
    content = TEMPLATE_METADATA_PATTERN.sub("", content)
    if replacements["CONFIRMED_CONSTRAINTS"]:
        content = CONDITIONAL_CONSTRAINT_PATTERN.sub(
            lambda match: match.group("body"), content
        )
    else:
        content = CONDITIONAL_CONSTRAINT_PATTERN.sub("", content)
    for key, value in replacements.items():
        content = content.replace("{{" + key + "}}", value)
    if UNRESOLVED_PLACEHOLDER_PATTERN.search(content):
        raise ValueError("Rule template contains an unresolved placeholder")
    return content.strip() + "\n"
