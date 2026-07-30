---
name: project-rules-init
description: Use when initially creating AI coding rules for an existing repository that has no trusted project-rules-bootstrap baseline.
---

# Project Rules Init

Create rules that let a new AI change this repository in the same style as its
existing maintainers. Project-specific coding behavior is the product;
framework inventory is only discovery input.

## Required shared resources

Read these before discovery:

- `../../references/code-chain-discovery.md`
- `../../references/rule-classification.md`
- `../../references/rule-content-contract.md`
- `../../references/confirmation-policy.md`
- `../../references/adapter-content-contract.md`
- `../../references/adapters.json`

Run the shared read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

If a trusted `.ai/rules-manifest.json` already exists, stop initialization and
use `project-rules-update`.

## Content-first workflow

1. Locate the repository root, existing assistant entry files, manifests,
   executable verification commands, and the scanner's cross-language
   candidates. Treat sensitive paths as existence-only.
2. Read candidate bodies. Trace representative complete code chains from
   entry or user action through interface, validation, business logic,
   persistence or integration, response handling, and tests. Follow imports
   and callers when the scanner only supplies a starting point.
3. Compare comparable implementations across modules. Promote stable repeated
   patterns directly, including legacy choices that differ from generic best
   practice. Record real conflicts and weak evidence separately.
   Stable repeated patterns are project rules, not confirmation questions.
4. Build rules around the questions a coding AI needs answered:
   **where to place** a change, **what to reuse**, what local shape and behavior
   to copy, what nearby surfaces must change with it, and **how to verify** it.
5. Produce a read-only **content preview** grouped by rule domain. Every
   proposed rule must contain Action, Scope, Project anchor, and Verification.
   Reject stack-only summaries, architecture inventories, and generic advice.
6. Escalate only the material risks named in the confirmation policy. Do not
   ask about role, preferences already answered by the repository, or stable
   repeated patterns.
7. Show the exact canonical and adapter file plan and request one write
   confirmation. After approval, render, write transactionally, validate, and
   report written, skipped, conflicted, and unverified items.

Use the current conversation language for generated prose unless the user
explicitly requests another language. Normal mode does not persist
`.ai/rules.analysis.md`; it is an optional strict-risk artifact, not a required
first write.
