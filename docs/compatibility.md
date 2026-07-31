# Adapter compatibility

`references/adapters.json` is the runtime registry. Each tool has one unique
output path and either `native` or `manual` support. Unknown tools produce no
adapter, and an existing unowned target is always `manual-only`.

| ID | Tool | Exact path | Support | Evidence checked |
| --- | --- | --- | --- | --- |
| `codex` | Codex | `AGENTS.md` | `native` | [OpenAI: custom instructions with AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md) |
| `claude-code` | Claude Code | `CLAUDE.md` | `native` | [Anthropic: project memory](https://docs.anthropic.com/en/docs/claude-code/memory) |
| `cursor` | Cursor | `.cursor/rules/project-rules.mdc` | `native` | [Cursor: rules documentation](https://docs.cursor.com/context/rules) |
| `trae` | Trae | `.trae/rules/project-rules.md` | `native` | [Trae: rules documentation](https://docs.trae.ai/ide/rules?_lang=en) |
| `codebuddy` | CodeBuddy | `.codebuddy/rules/project-rules/RULE.mdc` | `native` | [CodeBuddy: rules documentation](https://www.codebuddy.ai/docs/ide/Rules) |
| `workbuddy` | WorkBuddy | `RULES.md` | `manual` | No verified native loader; explicitly selected manual pointer only |

All entries were last reviewed on 2026-07-31. WorkBuddy's `RULES.md` must be
explicitly referenced; no native loading claim is made. The registry contains
no Generic fallback and no shared multi-consumer path.

Compatibility refreshes must use current vendor documentation. Update the
registry, template, tests, this page, and both READMEs together. Do not publish
an inferred path or loading claim.
