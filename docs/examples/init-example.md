# Initialization example

This abbreviated conversation shows an initialization session stopping at both
write gates. Text under **Agent** is a representative shape, not a promise that
every repository produces the same questions or files.

## Request and read-only discovery

**User**

> Initialize AI project rules for this monorepo. I am a project member. Use
> Codex and Cursor. Generate the rules in Chinese. Inspect the repository, but
> do not write anything until I approve.

**Agent**

> Mode and role
>
> - Mode: initialization
> - Role: project member
> - Generated rule language: Chinese
>
> Project profile
>
> - Local evidence shows a frontend package and a backend package.
> - Ownership of shared business logic is unresolved.
>
> High-risk questions
>
> 1. Which package owns shared business logic?
>
> Low-risk questions
>
> None.
>
> Selected adapters and support modes
>
> - `codex` — Codex — `AGENTS.md` — `native-auto`
> - `cursor` — Cursor — `.cursor/rules/*.mdc` — `native-auto`
>
> Proposed analysis path:
> `<project-root>/.ai/rules.analysis.md`
>
> **Gate 1: no files have been written. May I write only this analysis file?**

The agent stops here. The adapter preview is read-only; it does not cross the
gate.

## Gate 1 approval

**User**

> Approve Gate 1. Write only `.ai/rules.analysis.md`. Shared business logic is
> owned by `services/core`.

**Agent**

> Completed: wrote `.ai/rules.analysis.md` with the confirmed ownership answer.
>
> Candidate review:
>
> - Facts and conventions are listed with evidence and scope.
> - No strong constraints were proposed.
> - Unknown items remain excluded from canonical rules.
>
> Exact final plan
>
> Create:
>
> - `.ai/rules-manifest.json`
> - `.ai/rules/project.md`
> - `.ai/rules/architecture.md`
> - `AGENTS.md`
> - `.cursor/rules/project.mdc`
>
> Modify:
>
> - None
>
> Unchanged:
>
> - Existing unowned documentation and source files
>
> Manual-only:
>
> - None
>
> Conflict/merge summary:
>
> - No existing rule files were discovered.
>
> **Gate 2: no canonical rule, Manifest, or adapter has been written. May I
> write exactly this plan?**

The agent stops a second time. Gate 1 approval does not imply Gate 2 approval.

## Gate 2 approval and validation

**User**

> Approve Gate 2 exactly as shown.

**Agent**

> Completed: wrote only the approved canonical files, Manifest, and selected
> adapters.
>
> Pending: none.
>
> Conflict: none.
>
> Manual-reference: none.
>
> Unverified: none from this scan.
>
> Validation: `python scripts/validate_outputs.py <project-root>` passed.

The generated rule files are in the selected language. Adapter filenames,
registry paths, and compatibility-level identifiers remain unchanged.
