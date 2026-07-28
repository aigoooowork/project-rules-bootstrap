# Security template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 8-35 lines. Source requirements: confirmed authentication, sensitive-data, or security-boundary evidence. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: secrets, vulnerability details, generic security checklists, and empty sections.

Correct: `- Keep credentials outside the observed source-control scope.` Incorrect: `- Follow all security best practices.`

# {{PROJECT_NAME}} security
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
