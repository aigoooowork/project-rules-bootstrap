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

Run the read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

If a valid `.ai/rules-manifest.json` version 2 baseline exists, stop and use `project-rules-update`.

## Workflow

1. Locate the repository root, existing AI instructions, real build/test
   commands, major modules, and sensitive paths. Record sensitive paths as
   existence-only; never read their values.
2. Read candidate source bodies. For every major module, trace at least one
   representative chain from its user, API, CLI, message, task, or library
   entry through validation, business logic, persistence/integration, returned
   state, and tests. Follow imports and callers beyond scanner hints.
3. Compare at least two comparable implementations when declaring a repeated
   convention. Capture concrete project structure, symbols, boundary behavior,
   data/error flow, shared consumers, and working verification commands.
4. Draft only actionable recipes containing **Action**, **Scope**, **Project
   anchor**, and **Verification**. Exclude stack-only summaries, directory
   listings, slogans, proposed architecture, and rules unsupported by code.
5. Group recipes by the repository's actual concerns. Generate only groups
   with useful content; do not force a fixed category list. Always produce
   `.ai/rules/index.md` as the canonical entry to those groups.
6. Resolve material uncertainty progressively. Ask one to three focused
   questions at a time, normally no more than five to ten total. Exclude an
   unresolved claim instead of publishing a guess.
7. Treat every proposed `MUST`, `NEVER`, `必须`, or `禁止` instruction as a
   separate strong-constraint decision. Show its exact action, scope, reason,
   exception policy, project evidence, and verification, then obtain explicit
   confirmation before including it.
8. Preview the rule content and exact `create` / `manual-only` plan. An existing
   unowned adapter file is `manual-only`; never overwrite it. Request one final
   write confirmation after all content and strong-constraint decisions are
   settled.
9. After approval, render the dynamic canonical files, selected unique
   adapters, and small v2 ownership manifest. Apply one preflighted write plan
   with the manifest last, then run `scripts/validate_outputs.py`.

Use the current conversation language unless the user requests another.
Never create or persist `.ai/rules.analysis.md`.
