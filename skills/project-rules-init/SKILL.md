---
name: project-rules-init
description: Use when initially creating AI coding rules for an existing repository that has no trusted project-rules-bootstrap baseline.
---

# Project Rules Init

Create actionable project rules for a new AI or team member from the repository's existing code patterns.

## Shared core

Read these plugin-shared resources before discovery:

- `../../references/rule-classification.md`
- `../../references/rule-content-contract.md`
- `../../references/confirmation-policy.md`
- `../../references/adapters.json`

Run the shared read-only scanner:

```text
python ../../scripts/scan_project.py <project-root>
```

If a trusted `.ai/rules-manifest.json` already exists, stop initialization and use `project-rules-update`.

The full content-first workflow is defined by the shared references. Use one content preview and one write confirmation in the normal path. Keep sensitive files existence-only and use the shared renderer, writer, and validator for approved outputs.
