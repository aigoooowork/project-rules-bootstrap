# Canonical rule content contract

Canonical rules live only in `.ai/rules/`. Render every file in the one
Manifest language selected by the user. `en` uses the English headings below;
`zh-CN` uses `适用范围`, `已确认事实`, `已确认的强约束`, `执行规则`, `验证方式`,
and `相关规则`. Never emit bilingual headings in a final file.

```text
# Domain
## Scope
## Confirmed facts
## Execution rules
## Verification
## Related rules
```

Include `## Confirmed constraints` (or the exact Chinese equivalent) only when
confirmed constraints apply. Do not emit an empty optional section or a domain
file with no reliable content.

Every Manifest rule needs exactly one canonical marker:
`<!-- rule-id: <stable-id> -->`. The marker occupies its own line and is
followed by exactly one top-level list-item body; blank lines may separate them
and indented continuations remain part of that one item. Inline markers and
markers embedded in headings are unbound occurrences: they do not establish a
rule's presence and cause validation to fail. The validator trims and
collapses Unicode whitespace in the body and Manifest `rule.text`, then
compares them exactly without changing case or punctuation. It never includes
a mismatched body in an error message. Every rule also needs a scoped,
observable action and evidence record; conventions need confirmation. A confirmed
constraint may appear in the applicable domain file, not only
`restrictions.md`, but it must be inside that file's confirmed-constraints
section. Its Manifest record must include scope, reason, exception policy,
verification, a confirmation ID unique to that constraint, and linked
`user-confirmation` evidence. The
matching confirmation record must name only that rule, use decision
`confirmed`, and have the identical scope. Status `confirmed` without that
record is not proof of confirmation.

The authoritative section vocabulary and mandatory-instruction detector live
only in `scripts/rule_contract.py`. A semantic section may appear at most once,
including when equivalent English and Chinese headings are mixed. English
`MUST` and `NEVER` are case-insensitive; Chinese `必须` and `禁止` are the
corresponding mandatory tokens. The detector scans both section headings and
section bodies. Any occurrence is a strong instruction and is valid only as a
marker-bound list item in the explicit confirmed-constraints section; a token
in a heading is therefore invalid. Diagnostics identify the section safely
without echoing an unrecognized malicious heading or rule body.

Do not present generic advice as fact, unconfirmed MUST/NEVER rules, large
source blocks, secrets, cross-domain content, vague quality slogans,
duplicated rules, adapter syntax, personas, future architecture presented as
current, or stale rules without an explicit stale marker.

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
