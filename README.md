# Project Rules Bootstrap

[简体中文](README.zh-CN.md)

Project Rules Bootstrap turns evidence from an existing repository into
actionable AI coding rules. It provides two Skills:

- `project-rules-init` creates the first trusted rule set.
- `project-rules-update` maintains a validated v2 rule set after code changes.

The output is not a framework summary. The Skills read real source bodies,
trace complete code chains, compare repeated implementations, and tell a new
AI where to place a change, what existing path to reuse, which boundaries and
consumers are affected, and how to verify the result.

## Core workflow

1. Scan the repository without executing target-project code.
2. Trace representative end-to-end chains in every major module.
3. Convert stable evidence into recipes with Action, Scope, Project anchor,
   and Verification.
4. Ask focused questions only for material ambiguity or conflicts.
5. Confirm every new or changed strong constraint separately.
6. Preview the exact output and request one final write confirmation.
7. Write only owned paths, install the small manifest last, and validate.

Sensitive files are existence-only. Symlinks, traversal, sensitive output
paths, stale ownership hashes, and unowned overwrites are rejected. Existing
unowned assistant files remain unchanged and are reported as `manual-only`.
Retired generated files use an exact, hash-guarded `delete-owned` plan. The
Skills never persist `.ai/rules.analysis.md`.

## Generated structure

Groups are chosen from actual project concerns, not a fixed ten-file list:

```text
<target-project>/
├── .ai/
│   ├── rules-manifest.json
│   └── rules/
│       ├── index.md
│       ├── <actual-concern>.md
│       └── <another-concern>.md
├── AGENTS.md                         # selected Codex adapter
├── CLAUDE.md                         # selected Claude Code adapter
├── .cursor/rules/project-rules.mdc  # selected Cursor adapter
├── .trae/rules/project-rules.md     # selected Trae adapter
├── .codebuddy/rules/project-rules/RULE.mdc
└── RULES.md                          # selected WorkBuddy manual adapter
```

`.ai/rules/` is the only semantic source. `index.md` lists only generated
groups. Adapters route to the index and never copy or modify canonical rules.

The v2 manifest stores project/source identity, owned output paths and hashes,
and explicit strong-constraint confirmations. It does not store analysis,
canonical rule bodies, shared-consumer adapter metadata, or a second rules
ledger.

## Adapter registry

| ID | Tool | Output path | Support |
| --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `native` |
| `claude-code` | Claude Code | `CLAUDE.md` | `native` |
| `cursor` | Cursor | `.cursor/rules/project-rules.mdc` | `native` |
| `trae` | Trae | `.trae/rules/project-rules.md` | `native` |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/project-rules/RULE.mdc` | `native` |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual` |

Unknown tools produce no adapter. See [compatibility](docs/compatibility.md)
for the evidence behind these paths.

## Commands

Run the deterministic scanner and output validator from the Skill root:

```text
python scripts/scan_project.py <project-root>
python scripts/inspect_symbol.py <project-root> <python-symbol>
python scripts/validate_outputs.py <project-root>
```

Run tests:

```text
python -m unittest discover -s tests -v
```

Validation uses evidence profiles: code/API/database/frontend/AI groups require
real paths, source-backed symbols, explicit multi-link chains, and commands;
tooling/documentation groups require real configuration, script, or document
anchors and commands without inventing a code chain. The Skill still verifies
selected commands against project configuration. See the
[five-stack benchmark](benchmarks/README.md) for the pinned comparison against
two other rule generators.

The scanner enforces bounded directory, file, byte, Git-record, and subprocess
budgets. It reports skipped, truncated, and unverified areas rather than
describing partial evidence as complete.

## License

Licensed under the [Apache License 2.0](LICENSE).
