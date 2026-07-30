# Project Rules Bootstrap

[简体中文](README.zh-CN.md)

Project Rules Bootstrap is an agent Skill for turning evidence from an existing
repository into reviewable AI coding instructions. It is intended for project
owners, maintainers, members, and newcomers who need one canonical rule set plus
small entry points for the coding assistants they actually use.

The Skills do not treat a directory layout, an absent file, or generic
engineering advice as a project rule. They read representative source bodies,
trace complete code chains, compare repeated implementations, and turn stable
project behavior into actionable instructions for a new coding AI.

## Safety and confirmation model

Discovery is read-only. During that phase, the Skill does not execute target
project code, tests, builds, hooks, or package scripts; install dependencies;
fetch remotes; read secret contents; or follow symlinks outside the project
root. Sensitive paths are recorded as existence-only evidence.

The normal path uses one write confirmation. Before it, the Skill shows the
actionable rule content, unresolved risks, selected adapters, and the exact
Create, Modify, Unchanged, and Manual-only plan. Stable repeated conventions
are accepted from project evidence without asking the user to approve the
project's own style. Questions are reserved for credible conflicts, security or
data-correctness choices, new strong constraints, insufficient evidence, and
unsafe writes.

Existing files are preserved unless a clearly owned managed block can be
merged safely. Each existing-file write requires validated ownership and an
exact current SHA-256 precondition. Approved outputs are staged before commit,
the Manifest is installed last, and a commit failure restores replacements and
removes newly created targets. Managed-block updates retain the existing BOM,
newline convention, markers, and every byte outside the owned region.

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

The exact output depends on discovered evidence, selected domains, and selected
assistants. A full plan can contain:

```text
<target-project>/
├── .ai/
│   ├── rules.analysis.md  (optional strict-risk artifact)
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
