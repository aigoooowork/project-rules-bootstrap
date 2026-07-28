# Rule classification

Classify each candidate from observed evidence before asking for confirmation.

| Type | Observable criteria | Evidence threshold | Output treatment |
| --- | --- | --- | --- |
| `fact` | A present project property, command, file, boundary, or configuration can be directly observed. | One direct, reproducible source; use two when sources disagree. | May be confirmed as a grouped low-risk fact. |
| `convention` | A repeated team choice is visible across comparable files, commits, or documented instructions. | At least two comparable observations, or one explicit project document. | Present by theme for confirmation. |
| `constraint-candidate` | A proposed prohibition, mandatory action, or exception would materially limit future work. | An explicit user proposal, or a concrete project signal with source and affected scope. Never infer one from absence or generic practice. | Keep out of canonical rules until explicitly confirmed. |
| `unknown` | Evidence is absent, too weak, inaccessible, or does not establish intent. | No threshold is met. | Ask only if the answer affects the requested output. |
| `conflict` | Credible sources make incompatible claims, including existing rule files and implementation. | Record both sources and the affected scope. | Do not merge into a rule until the user resolves it. |

Evidence records identify the path or local Git datum, observation, scan time, and confidence. A single example never proves a convention; a missing example never proves a prohibition.
