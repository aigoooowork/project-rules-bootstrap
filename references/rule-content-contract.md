# Canonical rule content contract

Canonical rules live only in `.ai/rules/`. Their primary reader is a new AI or
team member who needs to make the next change in the repository without
introducing a second coding style.

## Content priority

A rule is useful only when it changes the reader's next action. Stack-only
statements such as "this project uses Flask", architecture inventories, and
generic advice such as "write clean code" are discovery evidence, not final
rules.

Every marker-bound rule recipe contains all four elements:

1. **Action**: what to do when making this kind of change.
2. **Scope**: the directories, file roles, modules, or task types where it applies.
3. **Project anchor**: an existing path, symbol, shared helper, or complete code
   chain to imitate.
4. **Verification**: a real command, focused search, consumer check, or manual
   comparison that proves the change still fits the project.

Use one top-level list item with indented continuations so the complete recipe
remains bound to one Manifest rule:

```markdown
<!-- rule-id: backend.add-business-endpoint -->
- Action: add the Resource in `backend/app/{module}/res_*.py`.
  - Scope: `backend/app/**`
  - Project anchor: `backend/app/preparation/res_preparation.py`
  - Verification: confirm the route remains registered by the module's
    `views_resource.py` and run its focused API test.
```

The complete normalized list-item body must match Manifest `rule.text`
exactly, preserving case and punctuation.

## Evidence threshold

A stable project pattern becomes a convention without a separate user
question when it has either:

- two comparable observations using the same pattern;
- one explicit project document;
- one effective configuration plus one real call site; or
- multiple consecutive links in a representative complete code chain.

Generic best practice does not override a stable project pattern. Ask the user
only when credible current sources conflict, the choice is a real security or
data-correctness question, a new strong constraint is proposed, or evidence is
too weak to guide future code safely.

## Canonical shape

Render every file in the Manifest language. `en` uses the English headings
below; `zh-CN` uses `适用范围`, `已确认事实`, `已确认的强约束`, `执行规则`,
`验证方式`, and `相关规则`. Never emit bilingual headings.

```text
# Domain
## Scope
## Confirmed facts
## Execution rules
## Verification
## Related rules
```

Include `## Confirmed constraints` only when confirmed constraints apply. Do
not emit empty optional sections or a domain file with no actionable rule
recipe.

## Marker and constraint integrity

Every Manifest rule has exactly one canonical marker:
`<!-- rule-id: <stable-id> -->`. The marker occupies its own line and is
followed by exactly one top-level list item. Inline markers and markers in
headings are invalid.

Every `MUST`, `NEVER`, `必须`, or `禁止` instruction belongs only in the
confirmed-constraints section. A confirmed constraint additionally requires
scope, reason, exception policy, verification, a unique confirmation ID, a
matching one-rule confirmation record, and linked `user-confirmation`
evidence. Status `confirmed` alone is not proof.

The authoritative heading vocabulary and mandatory-instruction detector live
in `scripts/rule_contract.py`. Diagnostics must not echo an unrecognized
malicious heading or mismatched rule body.

## Domain routing

| Domain | Include | Exclude |
| --- | --- | --- |
| `project` | First-read routing, real run/build commands, task entry points. | Stack-only summaries and detailed domain rules. |
| `architecture` | Placement, dependency direction, extension points, shared impact. | Directory inventories and future architecture. |
| `coding-style` | Repeated naming, file organization, logging, errors, comments, formatting. | Copied language guides and aesthetic slogans. |
| `frontend` | Page/component placement, state, request, route, and style recipes. | Backend persistence and generic UX advice. |
| `backend` | Interface, business, integration, transaction, and exception recipes. | Unevidenced layer prohibitions. |
| `api` | Input, output, auth, error, and compatibility contracts with call-site anchors. | Database implementation and REST tutorials. |
| `database` | Connection, query/ORM helpers, parameters, migrations, paging, transactions. | Credentials and generic SQL advice. |
| `testing` | Change-to-test mapping, commands, working directories, fixtures, pass criteria. | Unconfirmed coverage quotas. |
| `security` | Observed authentication, authorization, and sensitive-data boundaries. | Generic security checklists and secret content. |
| `restrictions` | Explicit project red lines with correct alternatives. | Ordinary habits, candidates, and guesses. |

Do not duplicate one semantic rule across domains or adapters. Adapters route
to canonical rules and never become another rule source.
