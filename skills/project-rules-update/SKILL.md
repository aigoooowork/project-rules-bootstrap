---
name: project-rules-update
description: Use when an existing project-rules-bootstrap v2 rule set needs an update after repository code, conventions, modules, or complete code chains have changed.
---

# Project Rules Update

Update canonical project rules from current code evidence. Preserve useful
rules and report semantic changes rather than treating every changed file as a
rule change.

## Required resources

Read:

- `../../references/update-workflow.md`
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

Use `python ../../scripts/inspect_symbol.py <project-root> <symbol>` when a
changed Python symbol's definition, import, or use ownership is material.

If no valid `.ai/rules-manifest.json` version 2 baseline exists, stop and use `project-rules-init`.

## Workflow

1. Validate the prior manifest and complete owned output tree. Preserve
   sensitive-file existence-only handling.
2. Accept optional user-provided repeated AI mistakes, recurring review
   feedback, new team decisions, or retirement notes as evidence candidates.
   Retain only long-lived, repeated, specific, actionable items; never import
   every comment as a rule. Strong candidates still require confirmation.
3. Compute the local Git delta when available. Read every changed body and
   trace each affected chain upstream, downstream, through persistence or
   integration, returned state, shared consumers, and focused tests. Use a
   bounded full scan when the delta is unreliable.
4. Compare current implementations with existing canonical recipes. Verify
   definition, import, use, configuration, and test locations. Keep a
   rule only when its Action, Scope, Project anchor, and Verification still
   reflect real code, including the symbol's actual callable/object role.
   Preserve unchanged rules without asking again.
5. Re-run the development-convention dimensions affected by changed source,
   tests, configuration, public boundaries, or generators. Create a temporary
   applicability assessment that either maps each applicable dimension to a
   project-anchored recipe or records an evidence-based omission. Do not force
   a convention rule or file, and do not turn a language default or isolated
   example into a project-wide decision.
6. Show a semantic delta classified as `added`, `modified`, `retired`, or
   `conflict`, with concrete paths and symbols. Formatting, movement, dependency
   versions, and architecture labels are not rule changes by themselves.
7. Regroup files only when actual concerns changed. Keep
   `.ai/rules/index.md` aligned with the groups that still contain actionable
   content; no fixed domain list is required. Update its compact evidence-based
   omission notes for applicable convention dimensions, without persisting the
   full assessment or empty categories.
8. Ask progressive focused questions only for credible conflicts, weak
   evidence that would mislead future work, security/data-correctness choices,
   or new/changed strong constraints. Bind every question to concrete anchors,
   the unresolved choice, and the affected rule. Any changed prohibition,
   mandatory action, approval prerequisite, or only-allowed path requires its
   own explicit confirmation; an unchanged validated confirmation is preserved.
9. If `project_evidence` reports affected specialties, read only their matching
   sections in `../../references/specialized-discovery.md` and re-run those
   discovery paths. Select the narrowest `RULE_TYPE` for each
   group; do not weaken code-chain validation by labeling it tooling or policy.
10. Preview the exact `create`, `replace-owned`, `delete-owned`, unchanged, and
   `manual-only` plan. Existing-file replacement or deletion requires
   ownership in the on-disk prior manifest plus the exact current SHA-256.
   Every retired generated path uses `delete-owned`; never overwrite or delete
   an unowned adapter.
11. Request one final write confirmation, apply the single preflighted plan with
   the manifest last, and validate the complete output tree.

Use the current conversation language unless requested otherwise. Never write
or retain `.ai/rules.analysis.md` as an update ledger.
