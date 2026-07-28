# Project template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-40 lines. Source requirements: direct configuration, files, or local Git evidence. Constraint-confirmation: only a confirmed Manifest constraint may appear. Forbidden: inferred business rules, detailed style rules, secrets, generic advice, and empty sections.

Correct: `- Run the observed test command from frontend/.` Incorrect: `- Always write clean code.`

# {{PROJECT_NAME}} project
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
