# Database template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-45 lines. Source requirements: observed access points, migrations, SQL dialect, or transaction configuration. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: credentials, production data, inferred operational limits, generic SQL advice, and empty sections.

Correct: `- Add schema changes through the observed migration directory.` Incorrect: `- Never use raw SQL.`

# {{PROJECT_NAME}} database
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
