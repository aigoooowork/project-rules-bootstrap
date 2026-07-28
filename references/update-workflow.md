# Update workflow

1. Re-check the user's role and permissions; update authority is not inferred from a prior run; ask the role question only once in the response. When both values are missing, combine the current-role and role-change-status request into one question, and do not repeat either item in later risk headings or the handoff.
2. Load the prior manifest and scan baseline, then compute a local Git baseline delta when Git is available.
3. If no usable baseline or Git history exists, use a bounded full scan and mark the fallback in the new baseline.
4. Reclassify changed evidence. For a constraint that is already canonical, has a valid prior confirmation, and has unchanged scope, action, reason, exception policy, verification, and constraint strength, preserve it without re-confirmation. First imports and semantic changes require explicit confirmation. Formatting-only changes do not.
5. Compare existing canonical rules and adapters. Assign each discovered existing rule file or clearly owned managed block exactly one merge classification: `preserved`, `additive`, `conflicting`, or `unsafe-to-merge`. Classify each file or block separately and include its path; Topic-level classification alone is insufficient. List conflicts with both sources and exclude unresolved conflicts from formal rules.
6. Reconfirm each new, first-imported, or semantically changed strong constraint. Do not ask for a new decision solely because an already-canonical confirmed constraint was carried forward unchanged.
7. Present the analysis delta and proposed files, then require the second explicit write gate before changing managed blocks or creating files.

Use a concrete table like this; keep the classification cell to exactly one enum and keep explanation and write state separate:

| Path or managed block | Classification | Reason | Write state |
| --- | --- | --- | --- |
| `.ai/rules/backend.md` | `preserved` | Confirmed canonical semantics are unchanged. | No write. |
| `.ai/rules/testing.md` | `additive` | New direct test-command evidence fits the owned file. | Proposed after Gate 2. |
| `AGENTS.md` managed block | `conflicting` | Existing routing disagrees with the selected registry adapter. | No write until resolved. |
| `CLAUDE.md` | `unsafe-to-merge` | No clearly owned managed block exists. | Leave untouched; offer a patch. |

Never overwrite an unowned file wholesale. If a managed region cannot be safely located, produce a proposed patch or candidate file instead of writing.
