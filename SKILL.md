---
name: project-rules-bootstrap
description: Use when initializing, generating, reorganizing, or updating AI coding instructions for an existing repository, especially when project structure, team conventions, rule conflicts, restrictive policies, or support across AGENTS.md, CLAUDE.md, Cursor, Trae, CodeBuddy, WorkBuddy, and other coding assistants must be discovered safely.
---

# Project Rules Bootstrap

## Core principle

Build project rules from local evidence and explicit decisions. Keep discovery read-only, keep unresolved items out of canonical rules, and cross each write gate only after the user approves that exact scope.

Follow the user's language in conversation. Generate all rule files in the one language the user selects.

## Safety boundary

During discovery:

- Never read secret contents. Treat sensitive paths as existence-only evidence, and ensure secret values are absent from responses and newly created or modified files.
- Never execute target-project code, builds, tests, hooks, or package scripts.
- Never install dependencies, fetch remotes, or require network access.
- Never follow a symlink outside the project root.
- Never write a target-project file before its gate.
- Never infer tool compatibility, project rules, or strong constraints.

A request such as "generate now without asking again" does not waive confirmation for a newly proposed strong constraint or either write gate. Inspecting a sensitive-file path is not permission to read its body.

## Workflow

### 1. Establish the session

Locate the repository root. Search within it for existing project instructions and adapter files, including registry-known paths, before proposing changes.

Before asking any question, resolve session state from the user request and existing evidence:

- Mode: initialization or update of an existing generated or hand-maintained rule set.
- Current role: project owner, project member, or newcomer.
- Selected coding assistants: allow multi-select and "all".
- Generated rule language: select one language for every generated rule file.

Mark every supplied value as answered. Ask only for values that remain missing, and never repeat an answered setup question later. If generated rule language is missing, ask the user to select it. Never infer generated rule language from the prompt language. Treat the role as local session state, not shared Manifest data.

In update mode, first read `references/update-workflow.md`. In every update session, ask whether the role changed before making update decisions:

- If prior local role state is available, show it, show any current role already supplied, and ask whether the role changed. Ask the current role only when still missing.
- If no prior local role is available, state that explicitly, show any current role already supplied or ask for it when missing, and ask whether this represents a known change or whether the change status is unknown.
- Ask this role check only once in the response. When both current role and change status are missing, combine them into one question and do not repeat either item under the later risk headings or handoff.

Role does not grant authority automatically.

### 2. Collect read-only evidence

Run the bundled scanner from the Skill directory:

```text
python scripts/scan_project.py <project-root>
```

Use its JSON as evidence, not as rule conclusions. Read relevant existing instruction files only when they are regular, non-sensitive files inside the root.

If Python is unavailable, use existing file-search and read-only local Git tools. Preserve the scanner's evidence shape: root; sorted file inventory with classification, `content_scanned`, content status, truncation, byte count, and reason; direct framework/toolchain signals; module manifests; scan-budget status; and bounded Git availability/status/commit records. Apply directory-entry, file-count, per-file-byte, total-content-byte, and subprocess-time budgets. Apply the scanner's exclusions for `.git`, dependencies, build outputs, caches, virtual environments, sensitive names, unreadable/binary files, and outside-root symlinks. Mark interrupted, truncated, skipped, or inaccessible areas explicitly. A language or toolchain signal alone does not establish a backend framework or architecture.

Treat `complete: false` as a partial scan. In particular, inspect
`limits.depth_truncated`, `unverified`, `unverified_summary`, and
`limits.unverified_paths_truncated`; a depth-limited path is not evidence that
the omitted file or framework is absent. Never read an omitted path body.
Keep the unverified-path list within the same directory-entry and
total-content-byte budgets as the scan; when that list cannot fit, retain the
bounded reason counts in `unverified_summary`.

### 3. Classify before asking

Read all three references before classifying any evidence:

- `references/rule-classification.md`
- `references/rule-content-contract.md`
- `references/confirmation-policy.md`

Classify each relevant item as `fact`, `convention`, `constraint-candidate`, `unknown`, or `conflict`, with its source path or local Git datum, observation, scan time, and confidence.

Use this decision rule:

| Evidence | Treatment |
| --- | --- |
| Direct present property | Fact |
| Repeated comparable choice or explicit project document | Convention |
| Proposed prohibition, mandatory action, or exception | Constraint candidate |
| Missing, inaccessible, or insufficient evidence | Unknown |
| Credible incompatible sources | Conflict |

Absence and generic practice are not rules. A handler plus repository directory does not prove service-layer, transaction, review, or database-access policy.

### 4. Resolve ambiguity efficiently

Ask only questions that affect the requested output. Use no more than ten questions in one round:

1. Use the explicit heading `High-risk questions` in English or `高风险问题` in Chinese. Put each architecture, ownership, data, security, dependency, and strong-constraint question in a separate item under it.
2. Use the explicit heading `Low-risk questions` in English or `低风险问题` in Chinese. Group remaining output-affecting questions by topic under it.
3. Reuse the session state from Step 1 and omit every question already answered by the user or evidence.
4. Ask fewer when evidence is sufficient.
5. Keep every unresolved high-risk ambiguity even when a shorter interaction was requested.

Show both headings even when one group has no questions, using `None` or its
language-equivalent for the empty group. End each round with one consolidated
unresolved list. Do not repeat answered questions in a handoff section.

### 4A. Read-only adapter preview

Before Gate 1, read `references/adapters.json` and show one preview row for
every selected assistant. A write gate blocks writes, not this read-only plan.
Each row must show:

- adapter ID and name;
- exact registry output path;
- support mode: `native-auto`, `import-supported`, `manual-reference`, or `unverified`;
- the explicit manual action when the support mode is `manual-reference`.

Use the registry value without guessing. `unverified` produces no adapter output. For CodeBuddy, show `native-auto` and
`.codebuddy/rules/<rule>/RULE.mdc`. For WorkBuddy, show `manual-reference` and
tell the user to import or `@` reference the root `RULES.md`; never invent a
native WorkBuddy rules path. If an assistant has no registry entry, list it
separately as unverified, invent no path or support mode, and generate no
adapter.

### 5. Preview analysis, then stop at Gate 1

Show this concise shape in conversation:

```text
Mode and role
Project profile
Confirmed facts
Pending conventions
Constraint candidates
Conflicts and unknowns
Selected adapters and support modes
Proposed analysis path: <project-root>/.ai/rules.analysis.md
```

Under `Selected adapters and support modes`, include the complete read-only
adapter preview from Step 4A. State exactly which analysis file would be
created or modified. Then stop and ask for explicit permission to write
`.ai/rules.analysis.md`. No approval means no write; report the preview as
completed and the file as pending.

After approval, render `assets/templates/analysis.md`, removing author-only comments, placeholders, and empty conditional sections.

### 6. Confirm candidate content

Present confirmations in this order:

1. Group low-risk facts with their evidence and scope.
2. Group conventions by domain.
3. Present each restrictive rule separately with candidate ID, scope, reason, exception, verification, and evidence.

Only use a fully displayed, scoped constraint batch when the user actively requests it. Keep rejected, deferred, unknown, and conflict items out of canonical rules.

For example, present "API handlers must never access the database directly" as a constraint candidate with its scope and verification. Do not add service orchestration, transaction ownership, mandatory review, or related backend rules unless separate project evidence or confirmation supports them.

```text
Candidate: restrictions.backend.repository-boundary
Scope: src/api/**
Reason/evidence: explicit user proposal; code layout alone does not confirm it
Exception: none proposed
Verification: inspect changed handlers for direct database calls
Decision: confirm, revise, reject, or defer
Write status: no files written
```

### 7. Plan exact outputs, then stop at Gate 2

Read these resources before rendering:

- `references/output-schema.md` for `.ai/rules-manifest.json`
- `references/adapter-content-contract.md` and `references/adapters.json` for selected adapters
- applicable files under `assets/templates/rules/` and `assets/templates/adapters/`

Show an exact final plan with four lists:

- Create
- Modify
- Unchanged
- Manual-only

Add a conflict/merge summary that assigns every discovered existing rule file
or clearly owned managed block exactly one of `preserved`, `additive`,
`conflicting`, or `unsafe-to-merge`. Classify each file or block separately;
topic-level classification alone is insufficient. Use the concrete per-file
table shape in `references/update-workflow.md`; keep reason and write state out
of the classification cell. Show any semantic change requiring reconfirmation.
Then stop and request explicit final write confirmation for that exact plan.

If approval is absent or narrower than the plan, do not write outside the approved scope.

### 8. Render only the approved files

Use `.ai/rules/` as the only canonical semantic source. Render only applicable domain files with `scripts/render_rules.py` so every heading uses the Manifest's exact `en` or `zh-CN` language. Render `.ai/rules-manifest.json` to the schema and keep personal identity out of it. Every semantic section appears at most once. Every Manifest rule has one unique canonical `rule-id` marker on its own line immediately followed by its single list-item body; inline markers and markers embedded in headings are invalid and do not establish presence. Normalize that body only by trimming and collapsing Unicode whitespace, then require an exact case- and punctuation-preserving match with Manifest `rule.text`. The authoritative headings, mandatory tokens, and normalization live in `scripts/rule_contract.py`.

Every `MUST`, `NEVER`, `必须`, or `禁止` instruction in either a section
heading or its body belongs only in the explicit confirmed-constraints
section. Every confirmed constraint, in any
canonical domain file, has a unique rule ID, scope, reason, exception policy,
verification, its own unique confirmation ID, user-confirmation evidence, and
a matching confirmed record with the same scope and only that one rule ID.
Reject a marker/body, Manifest, confirmation, scope, or evidence mismatch
without echoing the rule body in an error.

Keep `RULES.md` short: human/generic navigation only. Generate only selected adapters from the exact current entries in `references/adapters.json`:

- Describe `native-auto` as automatic only when the registry says so.
- Give every `manual-reference` adapter explicit import or `@` reference guidance.
- Use CodeBuddy's registry path and format: `.codebuddy/rules/<rule>/RULE.mdc`.
- Treat WorkBuddy as `manual-reference` unless refreshed official metadata proves otherwise.
- Do not promote stale or unverified metadata. A live refresh is optional; if performed, use official sources only.
- If a selected tool has no registry entry, mark it `unverified`, invent no path or loading behavior, and generate no adapter for it.
- Resolve selected adapters through `scripts/adapter_registry.py` before reading or writing an adapter path. Manifest ID, registry version, path, template, scope/loading, import mode, support, and consumers must match the trusted registry. Reject absolute, parent-traversal, sensitive, symlinked, or outside-root targets.
- When WorkBuddy and Generic are both selected, use their registry `shared_output` contract: render root `RULES.md` once with WorkBuddy as the concrete owner and record both consumer IDs in the single Manifest adapter entry. Never overwrite the same output twice.

Remove author-only comments, placeholders, and empty conditional sections. For a shared adapter template, use the selected registry entry's identity, support, scope, and loading metadata; `scripts/render_adapters.py` contains the deterministic rendering helper.

Preserve existing rule files. Merge only inside clearly owned managed blocks. If safe ownership or merge boundaries cannot be proven, create a proposal or patch outside the existing file and leave the original unchanged.

When Python is available, apply Gate 1 and Gate 2 changes through
`scripts/write_outputs.py`. Its analysis operation accepts only
`.ai/rules.analysis.md`; creating it uses `create`, while updating it uses
`replace-owned` only after the complete prior Manifest/output tree validates;
the prior Manifest's strict `analysis_ownership` record must identify version
`1.0`, owner `project-rules-bootstrap`, the reserved path, and the exact
current SHA-256. A caller hash is only a concurrency precondition, not
ownership provenance; an older Manifest without this ledger requires explicit
migration or ownership re-confirmation. Its final operation preflights the
exact approved path set, never writes the Gate 1 analysis path, and requires
the final Manifest ledger to match the approved analysis bytes. Every planned write is explicitly `create`,
`replace-owned`, or `managed-block`: `create` requires an absent path;
`replace-owned` requires a structurally valid prior Manifest/output tree plus
validated ownership and the exact current SHA-256; and `managed-block`
requires the exact current file SHA-256 and exactly one ordered managed-marker
pair. On initialization, a managed block additionally requires the new
Manifest to validate against the authoritative registry and authorize that
exact adapter path; an absent provenance object never means permissive.
Existing Manifest and canonical files are never replaced without the
validated prior state. Canonical roots and candidates are rejected before
reading when they are linked, reparse-point, sensitive, or outside the root.
Portable planned paths and every handle-relative child name reject `:` so
Windows alternate data stream syntax cannot be written.
All validation and write mutations use retained directory handles with
handle-relative no-follow operations (`dir_fd`/`O_NOFOLLOW` on POSIX and
native `RootDirectory` operations on Windows); missing required POSIX flags or
handle-relative filesystem capabilities make the safe backend unavailable and
fail closed. The analysis parent and file handles remain pinned until the same
file and namespace identity are rechecked immediately before the Manifest,
which is installed last. All writes are fully staged in same-directory temporary files,
existing targets are atomically claimed and identity/hash checked without
following links, and any commit failure rolls back replacements and deletes
creates. If rollback itself fails, preserve the unrecovered backup and emit a
root-level `.project-rules-bootstrap-recovery-*.json` path/state journal with
no file contents. Once every planned output is installed, later backup cleanup
failure is recoverable housekeeping: keep the committed result, retain the
artifact, close all handles, warn, and write a content-free
`.project-rules-bootstrap-cleanup-*.json` journal.
Managed-block updates preserve the original UTF-8 BOM,
newline convention, and every byte before the start marker and from the end
marker onward. A missing, duplicate, nested, reversed, symlinked, unowned, or
hash-mismatched target fails closed.

### 9. Update-specific delta

Prefer the stored Git scan baseline from the prior Manifest. Reclassify the local delta. Before preserving a constraint without re-confirmation, validate the complete prior Manifest with the current schema and verify the prior rule ID, text, type, scope, status, confirmation ID, confirmed decision, one-rule reference, matching scope, and linked user-confirmation evidence. Then compare the current rule's normalized semantic fields. Caller-supplied booleans or self-reported `confirmed` status are not proof. Only a validated unchanged prior constraint is exempt; missing/forged records, first imports, and text, scope, or other semantic changes require explicit confirmation.

Fall back to a bounded full scan when the baseline is missing, local Git is unavailable, or project structure/stack changed materially. Record the fallback reason and mark anything not rechecked as unverified.

### 10. Validate and report

Run:

```text
python scripts/validate_outputs.py <project-root>
```

Fix only generated-content contract failures within the confirmed scope. Do not change user-owned content or expand the approved plan to make validation pass.

Report these sections separately:

- Completed: files actually written and validation passed.
- Pending: decisions or approvals still required.
- Conflict: unresolved sources and untouched files.
- Manual-reference: explicit loading/import action for each selected manual adapter.
- Unverified: skipped, inaccessible, stale, or fallback-scanned areas.

Never claim a file was generated when no write occurred.

## Checkpoints

| Checkpoint | Required evidence | Allowed write |
| --- | --- | --- |
| Discovery | Scanner/fallback inventory and classifications | None |
| Gate 1 | Analysis preview and exact analysis path | `.ai/rules.analysis.md` only |
| Confirmation | Confirmed facts, conventions, constraints; unresolved items excluded | None beyond approved analysis |
| Gate 2 | Exact file plan plus conflict/merge summary | Exact approved canonical, Manifest, and adapter files |
| Validation | Validator output | Confirmed-scope generated fixes only |

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Short question list repeats answered items | Group by risk and end with one deduplicated unresolved list. |
| Update starts from files before checking role | Show the prior local role and ask whether it changed first. |
| A strong user instruction is treated as confirmed | Present the candidate's full scope and request explicit confirmation. |
| Generic backend practice becomes project policy | Require project evidence or explicit confirmation for each rule. |
| CodeBuddy and WorkBuddy receive equivalent native files | Use each registry entry's exact path, format, and support mode. |
| A sensitive path is opened to "verify" it | Record existence and `content_scanned: false`; never read the body. |
| A proposed file is reported as created | Separate planned, written, and validated states. |
| A depth-limited scan is described as complete | Report `depth_truncated`, bounded `unverified` paths or `unverified_summary`, and `complete: false`. |
| An existing output is put in a generic Modify list | Declare `replace-owned` or `managed-block` and show the current SHA-256 precondition. |

## Red flags: stop

- A target-project write is about to occur before its applicable gate.
- A constraint candidate is about to enter canonical rules without a matching explicit confirmation record.
- An unresolved conflict or unknown is about to become a rule.
- A secret body, target-project command, remote operation, dependency installation, or outside-root symlink is about to be accessed.
- An existing unowned file is about to be overwritten because a safe managed merge cannot be proven.

At any red flag, stop the action, preserve the read-only result, and ask for the missing decision or report the safe fallback.
