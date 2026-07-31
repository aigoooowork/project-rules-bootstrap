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

Run the read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

If no valid `.ai/rules-manifest.json` version 2 baseline exists, stop and use `project-rules-init`.

## Workflow

1. Validate the prior manifest and complete owned output tree. Preserve
   sensitive-file existence-only handling.
2. Compute the local Git delta when available. Read every changed body and
   trace each affected chain upstream, downstream, through persistence or
   integration, returned state, shared consumers, and focused tests. Use a
   bounded full scan when the delta is unreliable.
3. Compare current implementations with existing canonical recipes. Keep a
   rule only when its Action, Scope, Project anchor, and Verification still
   reflect real code. Preserve unchanged rules without asking again.
4. Show a semantic delta classified as `added`, `modified`, `retired`, or
   `conflict`, with concrete paths and symbols. Formatting, movement, dependency
   versions, and architecture labels are not rule changes by themselves.
5. Regroup files only when actual concerns changed. Keep
   `.ai/rules/index.md` aligned with the groups that still contain actionable
   content; no fixed domain list is required.
6. Ask progressive focused questions only for credible conflicts, weak
   evidence that would mislead future work, security/data-correctness choices,
   or new/changed strong constraints. A changed `MUST`, `NEVER`, `必须`, or
   `禁止` action, scope, reason, exception, or verification requires its own
   explicit confirmation; an unchanged validated confirmation is preserved.
7. Preview the exact `create`, `replace-owned`, `delete-owned`, unchanged, and
   `manual-only` plan. Existing-file replacement or deletion requires
   ownership in the on-disk prior manifest plus the exact current SHA-256.
   Every retired generated path uses `delete-owned`; never overwrite or delete
   an unowned adapter.
8. Request one final write confirmation, apply the single preflighted plan with
   the manifest last, and validate the complete output tree.

Use the current conversation language unless requested otherwise. Never write
or retain `.ai/rules.analysis.md` as an update ledger.
