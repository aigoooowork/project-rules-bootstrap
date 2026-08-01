# Canonical rule content contract

Canonical semantics live only in `.ai/rules/`. The output must help a new AI
make a real change without inventing another project structure or coding style.

## Actionable recipe

Every rule recipe contains:

1. **Action** — what to add, change, or reuse.
2. **Scope** — the modules, paths, roles, or task types where it applies.
3. **Project anchor** — real paths, symbols, comparable implementations, or a
   complete code chain to follow.
4. **Verification** — a real command, test scope, consumer check, or concrete
   comparison.

```markdown
<!-- rule-id: backend.add-business-endpoint -->
- Action: add the Resource beside `backend/app/preparation/res_preparation.py`.
  - Scope: `backend/app/**`
  - Project anchor: follow Resource → service → repository → response and its
    focused API test.
  - Verification: run the observed API test from `backend/` and inspect route
    registration in the module's `views_resource.py`.
```

Reject stack-only facts, directory inventories, generic advice, proposed
architecture stated as fact, and any recipe without a project anchor.

## Evidence threshold

Promote a stable convention without a separate question when supported by two
comparable observations, one explicit project instruction, one effective
configuration plus a real call site, or multiple consecutive links in a
representative complete code chain. A single example does not prove a general
convention; absence never proves a prohibition.

## Dynamic grouping

Generate `.ai/rules/index.md` plus only the groups the evidence needs. Groups
may describe frontend flows, API contracts, persistence, testing, deployment,
message processing, observability, module-specific extension points, or another
real project concern. They are not a mandatory category list. Omit empty groups
and do not duplicate one semantic rule across files or adapters.

Each group uses one output language and these sections:

```text
# Project — Group
## Scope
## Confirmed facts
## Confirmed constraints   (only when non-empty)
## Execution rules
## Verification
## Related rules
```

Chinese headings are `适用范围`, `已确认事实`, `已确认的强约束`, `执行规则`,
`验证方式`, and `相关规则`.

Place one evidence-profile marker immediately after the title:

```text
<!-- rule-type: code-chain -->
```

Choose the narrowest profile supported by the group:

| `RULE_TYPE` | Required grounding |
| --- | --- |
| `code-chain`, `api`, `database`, `frontend`, `ai` | At least two real paths, two real symbols, one multi-link chain, and a real verification command. |
| `tooling`, `documentation` | At least two real configuration/script/document paths and a real verification command; code symbols are optional. |
| `policy` | At least one real configuration, tooling, or documentation anchor plus explicit confirmation where the content is a strong constraint; a code chain is not required. |

Do not label code behavior as `tooling` or `policy` to bypass chain evidence.

## Strong constraints

Every prohibition, mandatory action, approval prerequisite, or only-allowed
path appears only under the confirmed-constraints section, regardless of its
wording. Its marker occupies one line and is followed by one list item. The v2
manifest stores a unique confirmation record containing
the rule ID, scope, normalized text SHA-256, reason, exception policy,
verification, and confirmation time. Status text or repository absence is not
confirmation.
