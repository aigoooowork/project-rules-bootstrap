# Compatibility

`references/adapters.json` is the authoritative registry for adapter IDs,
paths, templates, loading metadata, support claims, verification dates, and
sources. Documentation and generated manifests must match it exactly.

## Compatibility levels

| Level | Meaning |
| --- | --- |
| `native-auto` | The registry records a native rules path that the tool loads according to the verified scope/loading behavior. Only registry entries at this level may be described as automatic. |
| `import-supported` | The tool has a verified import mechanism, but loading requires an import step. There are currently no registry entries at this level. |
| `manual-reference` | The user must explicitly import or reference the documented file for the task. This is not automatic loading. |
| `unverified` | No current registry entry proves a path or loading behavior. The Skill invents neither and generates no adapter for that tool. |

The output Manifest schema accepts these four levels. The read-only adapter
preview uses the current registry value. A tool absent from the registry is
reported separately as `unverified`, not promoted to another level.
`unverified` never produces adapter output.

## Verified registry

All current entries were verified on `2026-07-28`.

| Adapter ID | Tool | Exact path | Scope loading | Import capability | Level | Official source |
| --- | --- | --- | --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `repository` | `native` | `native-auto` | [Introducing Codex](https://openai.com/index/introducing-codex/) |
| `claude-code` | Claude Code | `CLAUDE.md` | `repository` | `native` | `native-auto` | [Claude Code memory](https://docs.anthropic.com/zh-CN/docs/claude-code/memory) |
| `cursor` | Cursor | `.cursor/rules/*.mdc` | `glob` | `native` | `native-auto` | [Cursor rules](https://docs.cursor.com/context/rules) |
| `trae` | Trae | `.trae/rules/*.md` | `glob` | `native` | `native-auto` | [Trae rules](https://forum.trae.cn/t/topic/52) |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/<rule>/RULE.mdc` | `per-rule` | `native` | `native-auto` | [CodeBuddy rules](https://www.workbuddy.cn/docs/ide/User-guide/Rules) |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual` | `explicit-reference` | `manual-reference` | [Rules guide](https://www.workbuddy.cn/docs/ide/User-guide/Rules), [Create Task](https://www.workbuddy.ai/docs/workbuddy/Create-Task) |
| `generic` | Generic | `RULES.md` | `manual` | `explicit-reference` | `manual-reference` | [Introducing Codex](https://openai.com/index/introducing-codex/) |

The WorkBuddy registry entry also records `.ai/rules/*` as an alternative
manual reference. The generated adapter path remains the root `RULES.md`.
Import or `@` reference `RULES.md`; do not assume a native WorkBuddy rules
directory.

The Generic entry is an explicit-reference fallback for a selected tool that
can be directed to `RULES.md`. It does not assert universal automatic support.
WorkBuddy and Generic declare one `rules-navigation` shared output. If both are
selected, WorkBuddy's higher registry priority owns one rendered `RULES.md`;
the single Manifest adapter record lists `generic` and `workbuddy` as
consumers. Generic alone may own the same neutral output. This prevents
ambiguous overwrites.

Claude Code's `CLAUDE.md` uses the documented plain import line
`@.ai/rules/project.md`, without a Markdown code span in the generated file.

## Refresh policy

Network access is not required during normal Skill execution. If compatibility
metadata is refreshed, use official sources only and update the registry,
documentation, template metadata expectations, unit tests, and behavior evals
together. A newer claim must not be published until its path and loading
behavior are verified.
