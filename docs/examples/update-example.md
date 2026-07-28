# Update example

This abbreviated conversation shows an update session preserving existing
files, checking role state, and stopping at both write gates.

## Request and read-only delta

**User**

> Update the AI project rules in this repository. My current role is project
> owner and it has not changed. Preserve existing content and show conflicts.
> We use CodeBuddy and WorkBuddy.

**Agent**

> Mode and role
>
> - Mode: update
> - Current role: project owner
> - Role change: no
>
> Delta summary
>
> - The stored Git baseline is available.
> - Backend routing changed after the baseline.
> - Existing rule files disagree about direct database access.
>
> High-risk questions
>
> 1. Should the conflicting database guidance be preserved as unresolved, or
>    should one source supersede the other?
>
> Low-risk questions
>
> None.
>
> Selected adapters and support modes
>
> - `codebuddy` — CodeBuddy —
>   `.codebuddy/rules/<rule>/RULE.mdc` — `native-auto`
> - `workbuddy` — WorkBuddy — `RULES.md` — `manual-reference`; import or `@`
>   reference the root `RULES.md`
>
> Proposed analysis path:
> `<project-root>/.ai/rules.analysis.md`
>
> **Gate 1: the target tree is unchanged. The existing analysis is a regular
> file at the exact reserved path, and its current SHA-256 is included as the
> `replace-owned` precondition. May I update only that analysis file?**

The agent stops. WorkBuddy is not described as automatically loading
`RULES.md`, and no native WorkBuddy path is invented.

## Gate 1 approval

**User**

> Approve Gate 1 only. Keep the database guidance unresolved.

**Agent**

> Completed: verified the current SHA-256 and updated only
> `.ai/rules.analysis.md`.
>
> The database conflict remains in the conflict section and is excluded from
> canonical rules.
>
> Exact final plan
>
> Create:
>
> - `.codebuddy/rules/project/RULE.mdc`
>
> Modify:
>
> - `.ai/rules-manifest.json`
> - `.ai/rules/project.md`
> - `RULES.md`
>
> Unchanged:
>
> - `AGENTS.md` — `conflicting`
> - `CLAUDE.md` — `conflicting`
> - `.cursor/rules/backend.mdc` — `conflicting`
>
> Manual-only:
>
> - WorkBuddy: after generation, import or `@` reference the root `RULES.md`
>
> Per-file merge summary:
>
> | Path or managed block | Classification | Reason | Write state |
> | --- | --- | --- | --- |
> | `.ai/rules/project.md` | `additive` | New confirmed project evidence fits the owned canonical file. | Proposed after Gate 2. |
> | `.ai/rules-manifest.json` | `additive` | The confirmed delta and selected adapters need recording. | Proposed after Gate 2. |
> | `RULES.md` managed block | `preserved` | The owned navigation block remains compatible. | Update only that block after Gate 2. |
> | `AGENTS.md` | `conflicting` | Existing routing disagrees with another source. | No write. |
> | `CLAUDE.md` | `conflicting` | Existing routing disagrees with another source. | No write. |
> | `.cursor/rules/backend.mdc` | `conflicting` | Existing database guidance is unresolved. | No write. |
>
> Operational write plan:
>
> | Path | Mode | Pre-update condition |
> | --- | --- | --- |
> | `.codebuddy/rules/project/RULE.mdc` | `create` | Path absent; no prior hash. |
> | `.ai/rules-manifest.json` | `replace-owned` | Prior Manifest/output tree validated; exact current SHA-256 shown. |
> | `.ai/rules/project.md` | `replace-owned` | Prior Manifest ownership and canonical body binding validated; exact current SHA-256 shown. |
> | `RULES.md` | `managed-block` | Registry-authorized path, one ordered marker pair, exact current file SHA-256 shown. |
>
> **Gate 2: no planned canonical or adapter changes have been written. May I
> write exactly this plan?**

The agent stops again. It does not interpret approval to update the analysis as
approval to merge rules.

## Gate 2 approval and report

**User**

> Approve Gate 2 exactly as shown.

**Agent**

> Completed: wrote the approved files and validation passed.
>
> Pending: the database guidance still requires a future decision.
>
> Conflict: `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/backend.mdc` remain
> untouched.
>
> Manual-reference: import or `@` reference the root `RULES.md` in WorkBuddy.
>
> Unverified: areas not rechecked are listed in the analysis and Manifest.

The `RULES.md` update preserves its BOM/newline convention and every byte
outside the managed markers. Any prior-state, path, marker, symlink, or hash
mismatch would stop the whole preflight before writing.

If a later decision changes rule scope, action, exception, verification, or
constraint strength, the semantic change requires confirmation again.
