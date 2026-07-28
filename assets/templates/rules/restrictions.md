# Restrictions template

Required sections: scope, confirmed facts, execution rules, verification, related rules. Conditional: confirmed constraints is required only when at least one confirmed constraint applies. Recommended length: 8-35 lines. Source requirements: explicit user confirmation plus supporting evidence. Constraint-confirmation: every restriction has a confirmed Manifest constraint and rule-ID comment. Forbidden: candidate restrictions, inferred MUST/NEVER rules, ordinary style habits, secrets, and empty sections.

Correct: `- Confirmed constraint: preserve the stated API boundary.` Incorrect: `- Never use direct storage access.`

# {{PROJECT_NAME}} restrictions
## 适用范围
{{SCOPE}}
## 已确认事实
{{CONFIRMED_FACTS}}
## 已确认的强约束
{{CONFIRMED_CONSTRAINTS}}
## 执行规则
{{EXECUTION_RULES}}
## 验证方式
{{VERIFICATION}}
## 相关规则
{{RELATED_RULES}}
