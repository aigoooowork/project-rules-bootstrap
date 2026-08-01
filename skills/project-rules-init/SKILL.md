---
name: project-rules-init
description: Use when initially creating AI coding rules for an existing repository that has no trusted project-rules-bootstrap v2 baseline.
---

# Project Rules Init

Create project rules that tell a new AI where a change belongs, which existing
implementation to copy, how the real code chain connects, and how to verify it.
Framework inventories and generic engineering advice are discovery notes, not
rules.

## Required resources

Read:

- `../../references/code-chain-discovery.md`
- `../../references/rule-classification.md`
- `../../references/rule-content-contract.md`
- `../../references/confirmation-policy.md`
- `../../references/adapter-content-contract.md`
- `../../references/adapters.json`

Conditionally read `../../references/development-conventions.md` only after the
scanner reports `project_evidence.development_conventions`.

Run the read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

For important Python symbols, verify ownership before drafting:

```text
python ../../scripts/inspect_symbol.py <project-root> <symbol>
```

If a valid `.ai/rules-manifest.json` version 2 baseline exists, stop and use `project-rules-update`.
If rules exist without a valid v2 manifest, run `validate_outputs.py` for a
bounded diagnosis. Treat legacy `rule-id` markers and all unowned files as
manual migration inputs; report them, but never relabel or overwrite them
without the normal preview and ownership safeguards.

## Workflow

1. Locate the repository root and inspect `project_evidence` for declared
   runtime/dependency versions, environment/config sources, command candidates,
   conditional specialty signals, and sensitive paths. Treat declarations as
   repository facts, not proof of the external production environment. Record
   sensitive paths as existence-only; never read their values.
2. Read `primary-source`, `test`, and `config-tooling` candidates before
   `docs-example` candidates. For every major module, trace at least one
   representative chain from its user, API, CLI, message, task, or library
   entry through validation, business logic, persistence/integration, returned
   state, and tests. Follow imports and callers beyond scanner hints.
3. Distinguish every important symbol's definition, import, main use,
   configuration source, and covering test. Use `inspect_symbol.py` for Python;
   use language-aware search for other languages. Never describe an import or
   use site as the definition site, or render a non-callable object/constant as
   a function merely to satisfy a chain marker.
4. Compare at least two comparable implementations when declaring a repeated
   convention. Capture concrete project structure, symbols, boundary behavior,
   data/error flow, shared consumers, and working verification commands.
5. Classify evidence as a directly observed fact, a repeated convention, a
   constraint candidate, an unknown, or a conflict. Current implementation does
   not establish a permanent future constraint.
6. If the scanner lists specialties, then read only the matching sections of
   `../../references/specialized-discovery.md` and verify each signal in source.
   Do not load this reference before scanning. Do not load every specialty by
   default or force a specialty rule file.
7. For every listed development-convention dimension, read the conditional
   reference and create a temporary applicability assessment. Mark the
   dimension as covered by a project-anchored recipe or give an evidence-based
   omission reason such as insufficient comparable source, unreadable config,
   or no relevant public/generated boundary. Do not force a convention rule or
   file, and do not treat language defaults as project decisions.
8. Draft only actionable recipes containing **Action**, **Scope**, **Project
   anchor**, and **Verification**. Exclude stack-only summaries, directory
   listings, slogans, proposed architecture, and rules unsupported by code.
   Give each group the narrowest applicable `RULE_TYPE` evidence profile.
9. Group recipes by the repository's actual concerns. Generate only groups
   with useful content; do not force a fixed category list. Always produce
   `.ai/rules/index.md` as the canonical entry to those groups. Add only compact
   evidence-based omission notes from the applicability assessment so users
   can distinguish intentional omissions from missed discovery; do not persist
   the full assessment or empty categories.
10. Resolve material uncertainty progressively. Every question must cite the
   observed anchors, state what cannot be determined, explain which candidate
   rule changes, and offer concrete choices with consequences. Ask one to three
   focused questions at a time, normally no more than five to ten total.
   Exclude an unresolved claim instead of publishing a guess.
11. Treat every proposed prohibition, mandatory action, approval prerequisite,
   or only-allowed path as a separate strong-constraint decision. Decide
   semantically whether it limits future choices; do not rely on keyword
   matching alone. Show its exact action, scope, reason, exception policy,
   project evidence, and verification, then obtain explicit confirmation.
12. Preview the rule content and exact `create` / `manual-only` plan. An existing
   unowned adapter file is `manual-only`; never overwrite it. Request one final
   write confirmation after all content and strong-constraint decisions are
   settled.
13. After approval, render the dynamic canonical files, selected unique
   adapters, and small v2 ownership manifest. Apply one preflighted write plan
   with the manifest last, then run `scripts/validate_outputs.py`.

Use the current conversation language unless the user requests another.
Never create or persist `.ai/rules.analysis.md`.
