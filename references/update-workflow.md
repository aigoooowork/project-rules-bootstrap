# Update workflow

1. Re-check the user's role and permissions; update authority is not inferred from a prior run; ask the role question only once in the response. When both values are missing, combine the current-role and role-change-status request into one question, and do not repeat either item in later risk headings or the handoff.
2. Load the prior manifest and scan baseline, then compute a local Git baseline delta when Git is available.
3. If no usable baseline or Git history exists, use a bounded full scan and mark the fallback in the new baseline.
4. Reclassify changed evidence. A semantic rule change (scope, action, exception, verification, or constraint strength) requires reconfirmation; formatting-only changes do not.
5. Compare existing canonical rules and adapters. Assign each discovered existing rule file or clearly owned managed block exactly one merge classification: `preserved`, `additive`, `conflicting`, or `unsafe-to-merge`. Classify each file or block separately and include its path; Topic-level classification alone is insufficient. List conflicts with both sources and exclude unresolved conflicts from formal rules.
6. Reconfirm every carried or changed strong constraint, including any previously confirmed constraint affected by the delta.
7. Present the analysis delta and proposed files, then require the second explicit write gate before changing managed blocks or creating files.

Never overwrite an unowned file wholesale. If a managed region cannot be safely located, produce a proposed patch or candidate file instead of writing.
