<!-- TEMPLATE METADATA — the renderer MUST remove this comment and every template-control comment. Render only populated sections; do not emit placeholders or empty headings.
Required: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints. Length: 10-50 lines. Sources: handler, service, repository, transaction, or exception boundaries. Constraints: require confirmed Manifest records. Forbidden: frontend rules, inferred layer prohibitions, database credentials, large code blocks. Correct: "Use the observed service boundary for this handler scope." Incorrect: "Handlers must never query storage." -->
# {{PROJECT_NAME}} backend
## 适用范围 / Scope
{{SCOPE}}
## 已确认事实 / Confirmed facts
{{CONFIRMED_FACTS}}
<!-- CONDITIONAL SECTION: if non-empty, render the body below without these delimiters; otherwise omit it.
## 已确认的强约束 / Confirmed constraints
{{CONFIRMED_CONSTRAINTS}}
-->
## 执行规则 / Execution rules
{{EXECUTION_RULES}}
## 验证方式 / Verification
{{VERIFICATION}}
## 相关规则 / Related rules
{{RELATED_RULES}}
