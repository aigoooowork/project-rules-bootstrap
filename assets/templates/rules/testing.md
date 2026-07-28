# Testing template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints only when applicable. Recommended length: 10-40 lines. Source requirements: observed test directories, commands, fixtures, CI, or pass criteria. Constraint-confirmation: require a confirmed Manifest constraint. Forbidden: unconfirmed coverage quotas, generic testing slogans, large test bodies, and empty sections.

Correct: `- Run the observed focused test command before editing this module.` Incorrect: `- Tests must have 100% coverage.`

# {{PROJECT_NAME}} testing
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
