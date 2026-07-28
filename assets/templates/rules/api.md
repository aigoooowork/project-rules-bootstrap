# API template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-45 lines. Source requirements: observed routes, request/response shapes, authorization, errors, or compatibility tests. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: database implementation detail, generic API tutorials, secrets, and empty sections.

Correct: `- Return the observed error envelope for this route family.` Incorrect: `- Build RESTful endpoints.`

# {{PROJECT_NAME}} API
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
