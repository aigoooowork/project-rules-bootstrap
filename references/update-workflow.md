# Update workflow

1. Re-check the user's role and permissions; update authority is not inferred from a prior run; ask the role question only once in the response. When both values are missing, combine the current-role and role-change-status request into one question, and do not repeat either item in later risk headings or the handoff.
2. Load the prior Manifest and scan baseline, validate the complete prior Manifest/output tree with the current validator, and capture the exact current SHA-256 for every proposed existing-file write. For an existing analysis, also require the strict Manifest `analysis_ownership` record to name version `1.0`, owner `project-rules-bootstrap`, path `.ai/rules.analysis.md`, and the same exact SHA-256. An older Manifest without that persistent ledger must be migrated through explicit ownership re-confirmation before Gate 1 replacement. A path, marker, or caller-provided ownership claim without this validation is not trusted. Then compute a local Git baseline delta when Git is available.
3. If no usable baseline or Git history exists, use a bounded full scan and mark the fallback in the new baseline. If depth or another budget omits paths, set the truncation field, list bounded `unverified` paths or a bounded summary, and do not describe the scan as complete.
4. Reclassify changed evidence. Treat a constraint as unchanged only when the validated prior rule ID, text, type, scope, status, confirmation ID, confirmed decision, one-rule reference, confirmation scope, and user-confirmation evidence all reconcile and the current normalized semantics are unchanged; then preserve it without re-confirmation. First imports, missing/forged records, and semantic changes require explicit confirmation. Formatting-only changes do not.
5. Compare existing canonical rules and adapters. Assign each discovered existing rule file or clearly owned managed block exactly one merge classification: `preserved`, `additive`, `conflicting`, or `unsafe-to-merge`. Classify each file or block separately and include its path; Topic-level classification alone is insufficient. List conflicts with both sources and exclude unresolved conflicts from formal rules.
6. Reconfirm each new, first-imported, or semantically changed strong constraint. Do not ask for a new decision solely because an already-canonical confirmed constraint was carried forward unchanged.
7. Present the analysis delta and proposed files, then require the second explicit write gate before any `create`, `replace-owned`, or `managed-block` operation.

Use a concrete table like this; keep the classification cell to exactly one enum and keep explanation and write state separate:

| Path or managed block | Classification | Reason | Write state |
| --- | --- | --- | --- |
| `.ai/rules/backend.md` | `preserved` | Confirmed canonical semantics are unchanged. | No write. |
| `.ai/rules/testing.md` | `additive` | New direct test-command evidence fits the owned file. | Proposed after Gate 2. |
| `AGENTS.md` managed block | `conflicting` | Existing routing disagrees with the selected registry adapter. | No write until resolved. |
| `CLAUDE.md` | `unsafe-to-merge` | No clearly owned managed block exists. | Leave untouched; offer a patch. |

Never overwrite an unowned file wholesale. If a managed region cannot be safely located, produce a proposed patch or candidate file instead of writing.

The approved write plan also states an operational mode and precondition:

| Path | Mode | Pre-update condition |
| --- | --- | --- |
| `.ai/rules.analysis.md` | `replace-owned` | Complete prior Manifest/output tree validates independently; its strict ownership ledger matches the exact reserved path and current file SHA-256; target is a regular non-symlink file. The caller hash is a concurrency check, not ownership provenance. |
| `.ai/rules/backend.md` | `replace-owned` | Current prior Manifest/output tree validates and the file SHA-256 matches. |
| `.ai/rules/testing.md` | `create` | Exact path is absent; no prior hash. |
| `AGENTS.md` managed block | `managed-block` | On update, the validated prior Manifest authorizes the path; on initialization, the validated new Manifest and authoritative registry authorize it. Exact current file SHA-256 and exactly one ordered marker pair. |

An existing Manifest triggers prior-state validation even when another planned
path is new. Files outside the exact approved plan remain byte-for-byte
unchanged. Managed-block writes preserve BOM/newline style and all bytes
outside the markers; missing, duplicate, nested, reversed, symlinked, unowned,
or hash-mismatched targets are rejected before writing. The writer stages the
complete approved set in same-directory temporary files, atomically claims and
rechecks existing targets without following links, and rolls back every
replacement and newly created target if any commit step fails.
Gate 2 never writes the analysis path; its final Manifest must refresh or retain
an `analysis_ownership` record matching the exact Gate 1 analysis bytes. The
writer pins that analysis file and its parent by handle through the transaction,
rechecks the same handle and namespace identity immediately before installing
the Manifest, and installs the Manifest last.
Directory traversal and every staging, commit, rollback, and cleanup mutation
are handle-relative and no-follow (`dir_fd`/`O_NOFOLLOW` on POSIX and native
`RootDirectory` operations on Windows), with fail-closed behavior when the
platform backend or any required POSIX flag/handle-relative operation is
unavailable. Portable output paths and every handle-relative child name reject
`:` so Windows alternate data stream syntax cannot enter a plan. If rollback
cannot restore an existing target,
the original backup remains in place and a root-level
`.project-rules-bootstrap-recovery-*.json` journal identifies the recovery
paths and states without copying file contents.
After the last planned output is installed, outputs are committed. A later
backup-cleanup failure does not undo or report failure for those committed
outputs; it retains the artifact, emits a warning, and writes a content-free
`.project-rules-bootstrap-cleanup-*.json` housekeeping journal.
