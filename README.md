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
managed block can be merged safely.

See the complete stopping behavior in the
[initialization example](docs/examples/init-example.md) and
[update example](docs/examples/update-example.md).

## Install as a Skill

Copy or clone this repository into the Skill directory used by your agent host,
preserving `SKILL.md`, `assets/`, `references/`, and `scripts/` together. For a
Codex installation using `CODEX_HOME`, the resulting layout is:

```text
$CODEX_HOME/
└── skills/
    └── project-rules-bootstrap/
        ├── SKILL.md
        ├── assets/
        ├── references/
        └── scripts/
```

If your host uses a different Skill directory, install the same folder there.
Reload the host if required, then ask it to initialize or update project rules
for a local repository. Installing the Skill alone does not install, select, or
load any target-project adapter; adapter loading follows the compatibility
level documented below.

## Use

An initialization request can provide known session choices up front:

```text
Initialize AI project rules for this repository. I am a project member.
Use Codex, Cursor, and Trae adapters. Generate the rule files in Chinese.
Inspect only; stop before writing until I approve each gate.
```

An update request can identify the existing generated rule set:

```text
Update this repository's AI project rules. My current role is project owner
and it has not changed. Compare the current repository with the stored scan
baseline, preserve unowned files, and show the delta before either write gate.
```

The Skill asks only for missing setup or output-affecting information. Generated
rule files use one language selected by the user; the Skill never infers that
language from the language of the request.

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
`RULES.md` is the registry entry point for a selected WorkBuddy or Generic
manual-reference adapter; it must be imported or explicitly referenced.

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

Definitions, verification dates, and official sources are in
[the compatibility guide](docs/compatibility.md).

## Python-free fallback

Python is recommended for the bundled deterministic scanner and output
validator. Run these commands from the installed Skill root:

```text
python scripts/scan_project.py <project-root>
python scripts/validate_outputs.py <project-root>
```

If Python is unavailable, the Skill falls back to read-only file search and
local Git inspection. It preserves the scanner evidence shape and exclusions,
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
