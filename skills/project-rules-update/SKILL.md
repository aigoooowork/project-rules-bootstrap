---
name: project-rules-update
description: Use when an existing AI coding rule set needs an update after repository code, conventions, modules, or complete code chains have changed.
---

# Project Rules Update

Update a trusted project-rules-bootstrap rule set from the repository's current code and local delta.

## Shared core

Read these plugin-shared resources before discovery:

- `../../references/update-workflow.md`
- `../../references/rule-classification.md`
- `../../references/rule-content-contract.md`
- `../../references/confirmation-policy.md`
- `../../references/adapters.json`

Run the shared read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

If a trusted `.ai/rules-manifest.json` does not exist, stop the update and use `project-rules-init`.

The full content-first workflow is defined by the shared references. Show semantic rule changes rather than a full repeated audit. Keep sensitive files existence-only and use the shared renderer, writer, and validator for approved outputs.
