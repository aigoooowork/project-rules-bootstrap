# Architecture template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-50 lines. Source requirements: module boundaries, dependencies, or documented architecture. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: future architecture as current, formatting rules, generic diagrams, secrets, and empty sections.

Correct: `- Keep the observed API-to-service dependency direction.` Incorrect: `- Replace the system with microservices.`

# {{PROJECT_NAME}} architecture
## 适用范围
{{SCOPE}}
## 已确认事实
{{CONFIRMED_FACTS}}
<!-- Conditional: render only when confirmed constraints apply.
## 已确认的强约束
{{CONFIRMED_CONSTRAINTS}}
-->
## 执行规则
{{EXECUTION_RULES}}
## 验证方式
{{VERIFICATION}}
## 相关规则
{{RELATED_RULES}}
