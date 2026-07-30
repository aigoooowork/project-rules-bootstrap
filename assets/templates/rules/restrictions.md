<!-- RULE RECIPE CONTRACT: Every rule contains Action, Scope, Project anchor, and Verification. Reject stack-only and generic rules; include the project's correct alternative. -->
<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints is rendered only when non-empty. Length: 8-35 lines. Sources: explicit user confirmation plus supporting evidence. Constraints: every restriction has a rule-ID marker bound to the exact Manifest text and a unique one-rule confirmation record. Forbidden: candidates, inferred MUST/NEVER rules, ordinary style habits, secrets. Correct: "Confirmed constraint: preserve the stated API boundary." Incorrect: "Never use direct storage access." -->
# {{PROJECT_NAME}} {{DOMAIN_TITLE}}
## {{SCOPE_HEADING}}
{{SCOPE}}
## {{FACTS_HEADING}}
{{CONFIRMED_FACTS}}
<!-- CONDITIONAL SECTION: if non-empty, render the body below without these delimiters; otherwise omit the entire module.
## {{CONSTRAINTS_HEADING}}
{{CONFIRMED_CONSTRAINTS}}
-->
## {{RULES_HEADING}}
{{EXECUTION_RULES}}
## {{VERIFICATION_HEADING}}
{{VERIFICATION}}
## {{RELATED_HEADING}}
{{RELATED_RULES}}
