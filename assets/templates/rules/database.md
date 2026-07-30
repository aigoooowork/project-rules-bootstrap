<!-- RULE RECIPE CONTRACT: Every rule contains Action, Scope, Project anchor, and Verification. Reject stack-only and generic rules. -->
<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 10-45 lines. Sources: access points, migrations, SQL dialect, or transaction configuration. Constraints: require marker-bound bodies matching Manifest text and unique one-rule confirmation records. Forbidden: credentials, production data, inferred limits, generic SQL advice. Correct: "Add schema changes through the observed migration directory." Incorrect: "Never use raw SQL." -->
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
