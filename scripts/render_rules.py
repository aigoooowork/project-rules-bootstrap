"""Render dynamic canonical rule documents and their stable index."""

import re
from typing import Iterable, Mapping

from scripts.rule_contract import LANGUAGE_HEADINGS, parse_confirmed_constraint_block


DOMAIN_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_VALUES = (
    "PROJECT_NAME",
    "SCOPE",
    "CONFIRMED_FACTS",
    "EXECUTION_RULES",
    "VERIFICATION",
    "RELATED_RULES",
)
INDEX_COPY = {
    "en": {
        "title": "{project} project rules",
        "intro": "Read the rule files that match the change you are making.",
        "section": "Rule groups",
    },
    "zh-CN": {
        "title": "{project} 项目规则",
        "intro": "根据当前改动读取对应的规则文件。",
        "section": "规则分组",
    },
}


def _safe_domain(domain: object) -> str:
    if not isinstance(domain, str) or DOMAIN_PATTERN.fullmatch(domain) is None:
        raise ValueError("domain must be a lowercase hyphenated slug")
    return domain


def _required_text(values: Mapping[str, object], field: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("rule document requires non-empty {}".format(field))
    return value.strip()


def render_rule_document(
    domain: str, language: str, values: Mapping[str, object]
) -> str:
    """Render one actionable canonical group without a fixed domain template."""
    safe_domain = _safe_domain(domain)
    headings = LANGUAGE_HEADINGS.get(language)
    if headings is None:
        raise ValueError("language must be en or zh-CN")
    content = {field: _required_text(values, field) for field in REQUIRED_VALUES}
    constraints = values.get("CONFIRMED_CONSTRAINTS", "")
    if not isinstance(constraints, str):
        raise ValueError("CONFIRMED_CONSTRAINTS must be text")
    if constraints.strip():
        parse_confirmed_constraint_block(constraints)
    sections = [
        (headings["scope"], content["SCOPE"]),
        (headings["facts"], content["CONFIRMED_FACTS"]),
    ]
    if constraints.strip():
        sections.append((headings["constraints"], constraints.strip()))
    sections.extend(
        (
            (headings["rules"], content["EXECUTION_RULES"]),
            (headings["verification"], content["VERIFICATION"]),
            (headings["related"], content["RELATED_RULES"]),
        )
    )
    title = safe_domain.replace("-", " ")
    blocks = ["# {} — {}".format(content["PROJECT_NAME"], title)]
    blocks.extend("## {}\n{}".format(heading, body) for heading, body in sections)
    return "\n\n".join(blocks) + "\n"


def render_rule_index(
    project_name: str, language: str, domains: Iterable[str]
) -> str:
    """Render the stable canonical entry from the groups that actually exist."""
    if not isinstance(project_name, str) or not project_name.strip():
        raise ValueError("project_name must be non-empty text")
    copy = INDEX_COPY.get(language)
    if copy is None:
        raise ValueError("language must be en or zh-CN")
    unique_domains = sorted({_safe_domain(domain) for domain in domains})
    if not unique_domains:
        raise ValueError("at least one canonical rule domain is required")
    links = "\n".join(
        "- [{}]({}.md)".format(domain.replace("-", " "), domain)
        for domain in unique_domains
    )
    return (
        "# {title}\n\n{intro}\n\n## {section}\n\n{links}\n".format(
            title=copy["title"].format(project=project_name.strip()),
            intro=copy["intro"],
            section=copy["section"],
            links=links,
        )
    )
