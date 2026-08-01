# Project-specific development conventions

Read this reference only when `project_evidence.development_conventions`
reports at least one language and applicable dimension. The scanner routes the
investigation; it does not prove a convention.

## Evidence rule

For each applicable dimension, compare repository-owned configuration and at
least two comparable implementation or test files. Promote a convention only
when supported by one of these combinations:

- an effective configuration plus code that follows it;
- two comparable implementations with the same project-specific choice;
- an explicit project instruction plus a real implementation or command;
- a public contract plus its focused test.

A language default, formatter default, dependency presence, or single example
is only a cue. Record both the dominant pattern and material exceptions. Do not
turn the dominant pattern into a prohibition unless the user confirms that
future alternatives are forbidden.

## Applicable dimensions

Inspect only the dimensions listed by the scanner:

| Dimension | Evidence to compare | Useful rule outcome |
| --- | --- | --- |
| `naming-and-case` | Declarations, exported/public symbols, internal helpers, schemas, generated names | Normal symbol/file naming plus project-specific exceptions |
| `formatting-and-imports` | Formatter/linter config, import blocks, generated-code exclusions | Real command, scope, grouping, and intentional ignores |
| `types-and-contracts` | Type-checker config, public signatures, DTO/schema types, null/error returns | Where strictness applies and how boundary types are expressed |
| `errors-logging-and-comments` | Comparable error paths, logger calls, comments/docstrings | Native error conversion, log context, and when explanation is expected |
| `tests` | Test config, neighboring tests, fixtures, snapshots, integration setup | Test placement, naming, assertion style, and focused command |
| `public-api-and-compatibility` | Export files, routes, CLI/public package entry, deprecation paths, contract tests | Files and tests that must change together for current public behavior |
| `generated-docs-and-artifacts` | Generator config/scripts, source documents, generated outputs, CI checks | Edit source vs generated target and regeneration command |
| `build-and-runtime` | Manifests, lockfiles, scripts, Docker/CI config | Working directory, supported runtime declarations, and real gates |

If a listed dimension has insufficient readable evidence, omit the proposed
rule and record the missing comparison in temporary analysis. Persist only a
concise evidence-based omission note in the canonical index so a later user can
distinguish intentional omission from missed discovery. Do not persist the full
assessment, a blank category, or generic advice.

## Conditional language cues

Use only the cues for languages reported by the scanner. These guide searches;
they are not default rules.

- **Python:** modules/packages, functions and classes, underscore-prefixed
  internals, constants, decorators, type-checker scopes, Ruff/Black/isort,
  pytest naming/fixtures/markers, public re-exports, docstrings.
- **JavaScript / TypeScript:** files and exports, functions/classes/hooks,
  type-only imports, ESLint/Prettier/Biome, `tsconfig` strictness, package
  scripts, unit/browser tests, generated clients and declaration files.
- **Vue / React:** component and composable/hook naming, props/events, state
  stores, templates/JSX, CSS/module conventions, story/demo exclusions, user
  interaction tests.
- **Go:** package and file naming, exported capitalization, initialisms,
  `gofmt`/`goimports`, error wrapping, table tests, build tags, generated files,
  `go test` scopes.
- **Java / Kotlin:** packages/classes/methods/constants, annotations, nullability,
  Checkstyle/Spotless/PMD, exception mapping, unit/integration test suffixes,
  Gradle/Maven tasks, generated sources.
- **Rust:** modules/types/functions/constants, `rustfmt`, Clippy allowances,
  `Result`/error types, feature flags, unit/integration/doc tests, generated
  bindings.
- **Other languages:** use repository configuration, multiple comparable source
  files, tests, public entry points, and build scripts. Never borrow another
  language's conventions.

## Rule shape

Write a convention as an actionable project recipe:

1. action to take when making a specific kind of change;
2. scope where the pattern applies;
3. configuration and comparable-code anchors;
4. important exception or generated boundary;
5. exact verification command and working directory.

Combine closely related conventions in an existing project concern when that
keeps the rule easier to retrieve. Create a separate group only when the
evidence is broad enough and developers would search for it independently.
Use the `convention` evidence profile for such a group; do not disguise it as
`tooling` or invent a call chain merely to satisfy `code-chain`.

Reject statements such as “follow PEP 8”, “use idiomatic Go”, “write clean
Java”, or “prefer clear names”. They do not encode a repository decision.
