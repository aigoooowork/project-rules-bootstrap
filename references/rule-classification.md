# Rule classification

Classify each candidate from observed evidence before deciding whether a
question is necessary.

| Type | Observable criteria | Evidence threshold | Output treatment |
| --- | --- | --- | --- |
| `fact` | A present project property, command, file, boundary, or configuration can be directly observed. | One direct, reproducible source; use two when sources disagree. | Use as discovery evidence; promote only when it changes future work. |
| `convention` | A repeated team choice is visible across comparable files, calls, tests, commits, or documented instructions. | At least two comparable observations, one explicit project document, one effective configuration plus a call site, or a representative complete code chain. | Convert directly into an actionable project rule; no separate confirmation is required. |
| `constraint-candidate` | A proposed prohibition, mandatory action, or exception would materially limit future work. | An explicit user proposal, or a concrete project signal with source and affected scope. Never infer one from absence or generic practice. | Keep out of canonical rules until explicitly confirmed. |
| `unknown` | Evidence is absent, too weak, inaccessible, or does not establish intent. | No threshold is met. | Ask only if the answer affects the requested output. |
| `conflict` | Credible sources make incompatible claims, including existing rule files and implementation. | Record both sources and the affected scope. | Do not merge into a rule until the user resolves it. |

Evidence records identify the path or local Git datum, observation, scan time,
and confidence. A single example never proves a convention; a missing example
never proves a prohibition. Generic best practice does not overrule a stable
project convention.

For naming, formatting, imports, types, errors, logging, comments, tests,
public APIs, generated artifacts, and build/runtime practices, apply the same
threshold across languages. A formatter or linter declaration is a fact; it
becomes an actionable convention when its scope and real command or code usage
are also verified. A language's customary style is never project evidence.
