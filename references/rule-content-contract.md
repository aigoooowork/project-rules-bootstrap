# Canonical rule content contract

Canonical rules live only in `.ai/rules/`. Each generated file uses this structure when it has applicable content:

```text
# Domain
## 适用范围 / Scope
## 已确认事实 / Confirmed facts
## 执行规则 / Execution rules
## 验证方式 / Verification
## 相关规则 / Related rules
```

Include `## 已确认的强约束 / Confirmed constraints` only when confirmed constraints apply. Do not emit an empty optional section or a domain file with no reliable content.

Every rule needs a scoped, observable action and evidence record; conventions also need confirmation. Constraints need a confirmed Manifest record and a rule-ID comment. Do not present generic advice as fact, unconfirmed MUST/NEVER rules, large source blocks, secrets, cross-domain content, vague quality slogans, duplicated rules, adapter syntax, personas, future architecture presented as current, or stale rules without an explicit stale marker.

| Domain | Include | Exclude |
| --- | --- | --- |
| `project` | Project type, stack, primary directories, commands, key documents. | Detailed style rules and inferred business rules. |
| `architecture` | Module responsibility, dependency direction, data flow, extension locations. | Formatting details and unconfirmed target architecture. |
| `coding-style` | Confirmed naming, formatting, errors, and comments. | Copied language style guides. |
| `frontend` | Pages, components, state, request layer, routes, styles. | Backend database rules and framework tutorials. |
| `backend` | Handlers, services, data access, transactions, exception boundaries. | Frontend rules and unevidenced layering prohibitions. |
| `api` | Routes, request/response, authorization, errors, compatibility. | Database internals and generic API tutorials. |
| `database` | Data access entry points, migrations, SQL dialect, transactions. | Credentials and unverified production information. |
| `testing` | Test directories, commands, layers, fixtures, pass criteria. | Unconfirmed coverage targets or mandates. |
| `security` | Confirmed auth, sensitive-data, and security handling boundaries. | Generic checklists, vulnerability details, and secrets. |
| `restrictions` | Confirmed constraints with scope, reason, exception, verification. | Candidates, guesses, and ordinary coding habits. |
