---
name: project-rules-update
description: Use when an existing AI coding rule set needs an update after repository code, conventions, modules, or complete code chains have changed.
---

# Project Rules Update

Update trusted generated rules when the repository's actual coding patterns
change. Preserve useful rules and show only the semantic rule delta.

## Required shared resources

Read these before discovery:

- `../../references/update-workflow.md`
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

If a trusted `.ai/rules-manifest.json` does not exist, stop the update and use
`project-rules-init`; in other words, use `project-rules-init` for an
untrusted or missing baseline.

## Content-first workflow

1. Validate the existing generated baseline and compute the local Git delta
   when available.
2. Read changed source bodies and trace every affected complete code chain
   upstream, downstream, and into tests. Use a bounded full scan only when a
   reliable delta is unavailable.
3. Compare current stable code patterns with the canonical rules. Do not turn
   file movement, dependency versions, or architecture labels into rules
   unless they change how an AI should implement code.
4. Present a compact semantic rule delta: `added`, `modified`, `retired`, and
   `conflict`. Preserve unchanged actionable rules without re-confirmation.
5. Apply the shared risk policy. Stable repeated conventions are not questions;
   credible conflicts, correctness risks, new strong constraints, and unsafe
   writes are.
6. Show the exact owned-file and adapter plan and request one write
   confirmation. After approval, write transactionally, validate the complete
   output tree, and report the result.

Keep sensitive files existence-only. Use the current conversation language
unless explicitly overridden. Normal mode does not rewrite or persist an
analysis ledger merely to record that an audit happened.
