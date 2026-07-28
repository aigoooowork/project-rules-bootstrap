# Confirmation policy

## Question rounds

Present unanswered items under explicit `High-risk questions` and `Low-risk
questions` headings, or `高风险问题` and `低风险问题` in Chinese. Show both
headings, omit every value already answered by the user or evidence, repeat no
question, and ask no more than ten questions in one round.

The scanner and preview are read-only. Before Gate 1 approval, keep the entire
target tree byte-for-byte unchanged: do not write an analysis, canonical rule,
manifest, navigation file, or adapter. After Gate 1 approval and before Gate 2
approval, only the exact approved analysis path may differ; keep every
canonical rule, manifest, navigation file, adapter, and all other target files
unchanged.

- Group related, low-risk `fact` items when their evidence and scope are shown together; the user may accept or correct the group.
- Ask for `convention` confirmation by coherent theme (for example, formatting or test layout), never as an unlabelled list of inferred rules.
- Ask for each strong constraint individually, including scope, reason, exception, verification, and its candidate ID.
- A user may initiate a clearly scoped batch confirmation. Restate its members and scope; do not add unrelated candidates.
- The first write gate is explicit approval of the analysis and selected proposed files. Until then, preserve a no-write outcome.
- The final write gate is explicit approval of the rendered rule and adapter changes after conflicts and constraints are resolved.
- If approval is withheld, ambiguous, expired by a material change, or limited to another scope, make no write and retain candidates only in the analysis.

Confirmation records record timestamp, decision, scope, rule IDs, and batch reason when used. They do not record a person name, email, account, or Git identity.
