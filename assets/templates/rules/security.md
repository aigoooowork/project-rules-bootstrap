<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 8-35 lines. Sources: confirmed authentication, sensitive-data, or security-boundary evidence. Constraints: require marker-bound bodies matching Manifest text and unique one-rule confirmation records. Forbidden: secrets, vulnerability details, generic security checklists. Correct: "Keep credentials outside the observed source-control scope." Incorrect: "Follow all security best practices." -->
# {{PROJECT_NAME}} {{DOMAIN_TITLE}}
## {{SCOPE_HEADING}}
{{SCOPE}}
## {{FACTS_HEADING}}
{{CONFIRMED_FACTS}}
<!-- CONDITIONAL SECTION: if non-empty, render the body below without these delimiters; otherwise omit it.
## {{CONSTRAINTS_HEADING}}
{{CONFIRMED_CONSTRAINTS}}
-->
## {{RULES_HEADING}}
{{EXECUTION_RULES}}
## {{VERIFICATION_HEADING}}
{{VERIFICATION}}
## {{RELATED_HEADING}}
{{RELATED_RULES}}
