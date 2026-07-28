<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 10-50 lines. Sources: handler, service, repository, transaction, or exception boundaries. Constraints: require confirmed Manifest records. Forbidden: frontend rules, inferred layer prohibitions, database credentials, large code blocks. Correct: "Use the observed service boundary for this handler scope." Incorrect: "Handlers must never query storage." -->
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
