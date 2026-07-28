# Update workflow

1. Re-check the user's role and permissions; update authority is not inferred from a prior run.
2. Load the prior manifest and scan baseline, then compute a local Git baseline delta when Git is available.
3. If no usable baseline or Git history exists, use a bounded full scan and mark the fallback in the new baseline.
4. Reclassify changed evidence. A semantic rule change (scope, action, exception, verification, or constraint strength) requires reconfirmation; formatting-only changes do not.
5. Compare existing canonical rules and adapters. Preserve additive content, list conflicts with both sources, and exclude unresolved conflicts from formal rules.
6. Reconfirm every carried or changed strong constraint, including any previously confirmed constraint affected by the delta.
7. Present the analysis delta and proposed files, then require the second explicit write gate before changing managed blocks or creating files.

Never overwrite an unowned file wholesale. If a managed region cannot be safely located, produce a proposed patch or candidate file instead of writing.
