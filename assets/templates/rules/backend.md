# Backend template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-50 lines. Source requirements: observed handler, service, repository, transaction, or exception boundaries. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: frontend rules, inferred layer prohibitions, database credentials, large code blocks, and empty sections.

Correct: `- Use the observed service boundary for this handler scope.` Incorrect: `- Handlers must never query storage.`

# {{PROJECT_NAME}} backend
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
