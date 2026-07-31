# Rule quality benchmark

This benchmark checks whether generated project rules describe the repository
that actually exists. It intentionally does not reward a long stack inventory
or generic software-engineering advice.

## Frozen inputs

| Stack | Repository | Commit | Star snapshot (2026-07-31) |
| --- | --- | --- | ---: |
| Vue | [vuejs/pinia](https://github.com/vuejs/pinia) | `9db71974a2e3681d10a7f0247a17de5d44e27b1c` | 14.7k |
| React | [react-hook-form/react-hook-form](https://github.com/react-hook-form/react-hook-form) | `8b5162173446e33648cf0d6ee28eb43a987c3af2` | 44.8k |
| Python | [fastapi/fastapi](https://github.com/fastapi/fastapi) | `95f8322ee1dcda7ceace7b1c4f6c9915b36d748f` | 101.1k |
| Go | [gin-gonic/gin](https://github.com/gin-gonic/gin) | `34dac209ffb6ef85cc78c5d217bbb7ad001d68fd` | 89.0k |
| Java | [spring-projects/spring-petclinic](https://github.com/spring-projects/spring-petclinic) | `88e37c15cf6fc8490b01bc3e8e2c800cec1ac272` | 9.4k |

The comparison versions are
[Eriemon/agents-md-generator](https://github.com/Eriemon/agents-md-generator)
at `e26d5675b30851dc15b027be7560b6fbc2173e8e` (v2.0.3) and
[netresearch/agent-rules-skill](https://github.com/netresearch/agent-rules-skill)
at `7a8185e8f5b0d3244f48cf330eb94b54c346e073` (v3.13.2).

## Common prompt and isolation

Each skill received a clean shallow checkout and the same instruction:

> Generate project rules using repository-verifiable facts only. Add no team
> policy that is not present in the checkout. Describe the real implementation
> chain and the exact verification path for a representative product change.

Runs were isolated by tool and repository. Generated files from one run were
not visible to another. No proposed strong constraint was supplied or
confirmed.

Exact generator entry points were:

```text
python <agents-md-generator>/scripts/python/render/render_agents.py <checkout> --write
bash <agent-rules-skill>/skills/agent-rules/scripts/generate-agents.sh <checkout> --style=thin
```

`project-rules-bootstrap` was run through the Init workflow because it is an
agent Skill rather than a one-command generator. Its five resulting canonical
rules are retained under [`evidence/project-rules-bootstrap/`](evidence/project-rules-bootstrap/).
Third-party generated template bodies are not republished; their SHA-256
identities, exact commits, ratings, and enumerated findings are retained in
`results.json`.

## Evaluation

Accuracy, complete-code-chain coverage, and executability use the same explicit
0–5 rubric for every generated result:

| Score | Accuracy | Complete code chain | Executability |
| ---: | --- | --- | --- |
| 5 | All material claims are repository-anchored with no contradiction. | At least three consecutive source-verified symbols plus owning files/tests. | Exact focused and full commands are verified in the pinned repository configuration. |
| 4 | One minor imprecision, without changing the implementation decision. | A complete chain with one weak or implicit link. | Exact focused command, but broader gates are incomplete. |
| 3 | Core stack and commands are mostly correct, with unsupported project policy. | A partial two-link implementation chain. | Real broad repository commands, but no exact focused command. |
| 2 | Material misclassification or multiple unsupported claims. | Symbol inventory without an execution chain. | Generic or unverified commands. |
| 1 | Wrong primary project type or mostly unusable guidance. | Directory inventory only. | Commands contradict the pinned repository. |
| 0 | No usable output. | No chain evidence. | No runnable command or no output. |

The grounding gate also requires at least two existing file anchors, two code
symbols, one explicit multi-symbol chain, and one verification command. A
reported path that is absent from the frozen source checkout is an invented
anchor.

The newcomer desk test has two probes per repository:

1. Can a new contributor identify the owning implementation path and at least
   three consecutive links for the representative change?
2. Can the contributor select a focused verification command from the rules?

A probe passes only from generated-rule evidence; repository exploration is
not allowed during scoring. This is a rule-only desk test, not a claim that ten
independent developers submitted production patches.

Reproduce the pinned scanner and grounding metrics after placing the five
checkouts and generated project-rules outputs under two local roots:

```text
python -m benchmarks.run_benchmark <checkouts-root> <outputs-root>
```

The checked-in snapshot is the runner's direct JSON result. It records scanner
limits, elapsed time, files, modules, truncation/failure flags, real file
anchors, source-verified symbols, explicit chain signals, and command-shaped
verification candidates. `scanner_anchor_coverage` is the fraction of final
rule path anchors that were already present in the scanner candidate paths; it
is a scanner-observability metric, not a rule-quality score.

## Aggregate result

| Skill | Coverage | Accuracy | Complete chain | Executability | Grounding gate | Conservative unsupported-policy findings | Noise | Newcomer probes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| project-rules-bootstrap | 5/5 | 5.0 | 5.0 | 5.0 | 5/5 | 0 | Low; 23 lines per project rule | 10/10 |
| agents-md-generator | 5/5 | 2.6 | 0.0 | 2.8 | 0/5 | at least 45 | High; 58-line median plus foreign governance | 0/10 |
| agent-rules-skill | 4/5 | 1.6 | 0.0 | 1.6 | 0/5 | at least 60 | Very high; 132.5-line median on generated roots | 0/10 |

The conservative findings count only clearly foreign or unsupported policy,
not every questionable recommendation. `agents-md-generator` imported local
Chinese response, naming, output-format, and workspace-governance rules into
all five unrelated projects; it also classified Spring PetClinic's primary
language as `script`. `agent-rules-skill` classified FastAPI as Flask, could
not generate the Java case, and emitted broad commit, merge, dependency, and
workflow prohibitions without repository evidence.

All five `project-rules-bootstrap` outputs identified a representative product
chain rather than only directories: Pinia store creation, React Hook Form
submission, FastAPI request routing, Gin HTTP dispatch, and PetClinic owner
search. Machine-readable measurements and per-project ratings are in
[`results.json`](results.json).

## Implementation consequence

The benchmark produced a new `scripts/rule_quality.py` gate. Validation now
rejects canonical rule files that contain only stack summaries or generic
advice, lack real file anchors and source-verified symbols, lack an explicit
multi-symbol chain, lack a command-shaped verification candidate, or cite a
path absent from the target checkout. The gate is dynamic; it does not add or
require a fixed generation template. Benchmark executability ratings also
manually check each candidate against the pinned repository configuration.
