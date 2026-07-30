# Project Rules Bootstrap

[简体中文](README.zh-CN.md)

Project Rules Bootstrap is an agent Skill for turning evidence from an existing
repository into reviewable AI coding instructions. It is intended for project
owners, maintainers, members, and newcomers who need one canonical rule set plus
small entry points for the coding assistants they actually use.

The Skill does not treat a directory layout, an absent file, or generic
engineering advice as a project rule. It scans local evidence, separates facts,
conventions, constraint candidates, unknowns, and conflicts, then asks the user
to decide what can become canonical.

## Safety and confirmation model

Discovery is read-only. During that phase, the Skill does not execute target
project code, tests, builds, hooks, or package scripts; install dependencies;
fetch remotes; read secret contents; or follow symlinks outside the project
root. Sensitive paths are recorded as existence-only evidence.

There are two independent write gates:

1. **Gate 1 — analysis:** the Skill previews its evidence, open questions,
   selected adapters, and the exact `.ai/rules.analysis.md` path, then stops.
   Only explicit approval permits that analysis file to be written.
2. **Gate 2 — canonical files and adapters:** after candidate content is
   decided and each conflict is either resolved or explicitly preserved and
   excluded, the Skill shows exact Create, Modify, Unchanged, and Manual-only
   lists plus a per-file merge summary, then stops again. Explicit approval
   permits only that exact plan to be written.

A request to “generate everything now” does not bypass either gate or confirm a
new strong constraint. Existing files are preserved unless a clearly owned
managed block can be merged safely. An update plan labels each write
`create`, `replace-owned`, or `managed-block`. Existing analysis, Manifest,
canonical, or adapter content is updated only after its exact path, validated
prior-tree ownership, and current SHA-256 precondition match; the hash is only
a concurrency check, never ownership provenance. Existing analysis additionally
requires a strict persistent Manifest ownership ledger; older manifests must be
migrated through explicit ownership re-confirmation. Gate 2 refreshes that
ledger to the exact approved analysis bytes. An initialization-time
managed block requires authorization from the validated new Manifest and
authoritative adapter registry. Validation, commit, and rollback use
handle-relative no-follow filesystem operations on both POSIX and Windows and
fail closed if any required safe-platform flag or handle-relative capability is
unavailable. Portable paths reject `:` to exclude Windows alternate data
streams. Gate 2 pins and rechecks the approved analysis through the final,
last-installed Manifest. All approved outputs
are staged before commit, and a commit failure restores replacements and
removes newly created targets. A failed rollback preserves its backup and
writes a content-free recovery journal with the artifact paths.
After all planned outputs are installed, a later backup-cleanup failure keeps
the committed outputs and writes a content-free cleanup journal plus warning.
Managed-block updates keep the UTF-8 BOM, LF/CRLF convention, and all bytes
outside the markers unchanged.

See the complete stopping behavior in the
[initialization example](docs/examples/init-example.md) and
[update example](docs/examples/update-example.md).

## Install as a plugin

Install this repository as one Codex plugin. It exposes two Skills while
keeping `assets/`, `references/`, and `scripts/` as one shared core:

```text
project-rules-bootstrap/
├── .codex-plugin/plugin.json
├── skills/
│   ├── project-rules-init/SKILL.md
│   └── project-rules-update/SKILL.md
├── assets/
├── references/
└── scripts/
```

`project-rules-init` creates the first trusted rule set.
`project-rules-update` maintains a rule set that already has a validated
project-rules-bootstrap baseline. Installing the plugin does not install,
select, or load any target-project adapter; adapter loading follows the
compatibility level documented below.

## Use

Use Init when a repository has no trusted generated rule set:

```text
Initialize actionable AI coding rules from this repository's existing code
patterns. Use Codex, Cursor, and Trae adapters.
```

Use Update after code or project conventions change:

```text
Update the existing AI coding rules from the current Git delta and affected
code chains. Preserve unowned files and show semantic rule changes.
```

## Generated target-project structure

The exact output depends on confirmed evidence, selected domains, and selected
assistants. A full plan can contain:

```text
<target-project>/
├── .ai/
│   ├── rules.analysis.md
│   ├── rules-manifest.json
│   └── rules/
│       ├── project.md
│       ├── architecture.md
│       ├── coding-style.md
│       ├── frontend.md
│       ├── backend.md
│       ├── api.md
│       ├── database.md
│       ├── testing.md
│       ├── security.md
│       └── restrictions.md
├── AGENTS.md
├── CLAUDE.md
├── .cursor/rules/<rule>.mdc
├── .trae/rules/<rule>.md
├── .codebuddy/rules/<rule>/RULE.mdc
└── RULES.md
```

Only applicable canonical domain files and selected adapters are generated.
`.ai/rules/` is the sole canonical semantic source. Adapter files are concise
routing entry points and do not duplicate or change canonical rules.
Each canonical `rule-id` marker stands on its own line and binds to its
immediately following single list-item body; inline and heading-embedded
markers are invalid. Deterministic whitespace normalization must produce the
exact Manifest `rule.text`. `MUST`, `NEVER`, `必须`, and `禁止` instructions
are detected in both headings and bodies and accepted only as marker-bound
items in the explicit confirmed-constraints section, with a unique one-rule
confirmation record, matching scope, and linked confirmation evidence.
`RULES.md` is the registry entry point for a selected WorkBuddy or Generic
manual-reference adapter; it must be imported or explicitly referenced. If
both are selected, the registry shared-output contract renders the file once,
uses WorkBuddy as the concrete owner, and records both consumers in one
Manifest adapter entry.

## Tool compatibility

Compatibility claims are copied from
[`references/adapters.json`](references/adapters.json), not inferred.

| Adapter ID | Tool | Exact registry path | Compatibility level |
| --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `native-auto` |
| `claude-code` | Claude Code | `CLAUDE.md` | `native-auto` |
| `cursor` | Cursor | `.cursor/rules/*.mdc` | `native-auto` |
| `trae` | Trae | `.trae/rules/*.md` | `native-auto` |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/<rule>/RULE.mdc` | `native-auto` |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual-reference` |
| `generic` | Generic | `RULES.md` | `manual-reference` |

For WorkBuddy, import or `@` reference the root `RULES.md`. Generic tools must
explicitly reference `RULES.md` using the mechanism provided by that tool.
Neither entry is automatic. Tools absent from the registry are `unverified`: no
path or loading behavior is invented, and no adapter is generated.

Claude Code's generated `CLAUDE.md` imports the canonical project router with
the plain line `@.ai/rules/project.md`.

Definitions, verification dates, and official sources are in
[the compatibility guide](docs/compatibility.md).

## Python-free fallback

Python is recommended for the bundled deterministic scanner and output
validator. Run these commands from the installed Skill root:

```text
python scripts/scan_project.py <project-root>
python scripts/validate_outputs.py <project-root>
```

The scanner enforces directory-entry, file-count, per-file-byte,
total-content-byte, Git-record, Git-byte, and subprocess-time budgets. Each
inventory row says whether content was scanned, skipped, truncated, or
unverified. Sensitive paths remain existence-only. Language/toolchain signals
are reported separately and never become backend conclusions by themselves.
When `max_depth` omits an entry (including `max_depth=0`), the scanner sets
`limits.depth_truncated`, returns `complete: false`, and records bounded
`unverified` paths without reading their bodies. The path evidence itself is
limited by the directory-entry and total-content-byte budgets; omitted evidence
still increments the bounded reason counts in `unverified_summary`.

If Python is unavailable, the Skill falls back to read-only file search and
local Git inspection. It preserves this bounded evidence shape and exclusions,
marks interrupted or inaccessible areas as `unverified`, and does not execute
target-project commands. The bundled validator cannot be run without Python, so
that limitation is reported rather than silently treated as a pass.

## Test and contribute

Run the repository unit and contract tests with:

```text
python -m unittest discover -s tests -v
```

Behavior scenarios and their expected assertions are declared in
`evals/evals.json`. This repository does not bundle a behavior-eval runner. Use
the Skill-evaluation workflow provided by your agent environment, or review
each prompt and expectation manually, checking that the fixture tree is
unchanged at each pre-approval write-gate stop.

Before contributing an adapter or changing documentation, read
[CONTRIBUTING.md](CONTRIBUTING.md). Adapter metadata, templates, official
sources, unit coverage, and behavior evals must be updated together without
changing canonical rule semantics.

## License

Licensed under the [Apache License 2.0](LICENSE).
