# Adapter content contract

`references/adapters.json` contains one small record per supported tool:
`id`, `name`, unique output `path`, `support`, and `template`.

Preview only the selected tools. Unknown IDs produce no output. Every adapter
routes to `.ai/rules/index.md` and contains no canonical rules, inferred
constraints, registry metadata comments, or another tool's syntax.

Each registry path is unique. Codex, Claude Code, Cursor, Trae, and CodeBuddy
use their registered native entry; WorkBuddy uses one root `RULES.md` manual
reference. There is no Generic consumer and no shared multi-consumer output.

If an adapter target already exists without prior v2 manifest ownership, mark
it `manual-only` and leave it unchanged. A generated adapter may be replaced
only when the prior manifest owns the exact path and its current SHA-256 still
matches. Reject absolute paths, traversal, sensitive names, and symlinks.
