<!-- RULE RECIPE CONTRACT: Every rule contains Action, Scope, Project anchor, and Verification. Reject stack-only and generic rules; stable repeated legacy style remains the project convention. -->
<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 10-35 lines. Sources: repeated comparable code or formatter configuration. Constraints: require marker-bound bodies matching Manifest text and unique one-rule confirmation records. Forbidden: copied language guides, quality slogans, large code blocks, secrets. Correct: "Match the configured formatter for files in this scope." Incorrect: "Use elegant names." -->
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
