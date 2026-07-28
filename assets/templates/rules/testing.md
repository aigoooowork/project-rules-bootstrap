<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 10-40 lines. Sources: test directories, commands, fixtures, CI, or pass criteria. Constraints: require marker-bound bodies matching Manifest text and unique one-rule confirmation records. Forbidden: unconfirmed coverage quotas, generic testing slogans, large test bodies. Correct: "Run the observed focused test command before editing this module." Incorrect: "Tests must have 100% coverage." -->
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
