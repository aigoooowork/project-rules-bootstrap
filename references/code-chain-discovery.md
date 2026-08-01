# Complete code-chain discovery

Use this reference in both Init and Update. The goal is not to name the
architecture. The goal is to learn how a new AI should place, connect, and
verify code so it looks native to the repository.

## Questions the discovery must answer

- Where to place a change of this kind?
- Which existing implementation should be imitated?
- What to reuse instead of creating a parallel helper, client, component, or
  infrastructure layer?
- Which request fields, return values, state, and errors cross each boundary?
- Which shared consumers may be affected?
- How to verify the change using the project's real commands and tests?

## Complete code chain

For each major module, trace at least one representative complete code chain:

```text
user or external event
→ page, CLI, HTTP, message, task, or library entry
→ route, controller, handler, resource, or command dispatch
→ parser, DTO, schema, or validation
→ business orchestration, service, use case, domain function, or core package
→ repository, DAO, mapper, SQL, ORM, file, cache, queue, or external service
→ result conversion and caller state update
→ focused tests, build checks, or manual acceptance
```

Also trace configuration, authentication, authorization, errors, logging, and
shared utilities when they participate in the chain.

## Representative sampling

Use `scripts/scan_project.py` to obtain `rule_discovery.candidates`. It provides
module, language, and role hints; it does not claim a complete call graph.

Read candidates by `scan_priority`: `primary-source`, `test`,
`config-tooling`, then `docs-example`. Examples can clarify public usage but do
not override the owning implementation. Use `project_evidence` for repository
runtime/dependency declarations, config sources, command candidates, and
conditional specialty routing. These are declared facts, not proof of the
external production environment.

For important Python symbols run
`python scripts/inspect_symbol.py <project-root> <symbol>` and report definition,
import, and use locations separately. For other languages use language-aware
search with the same distinction. A file that imports a symbol does not own its
definition.

When `project_evidence.specialized_discovery` is non-empty, read
`specialized-discovery.md` only for the listed specialties and verify each
dependency/path signal against source before drafting.

1. Give every major module a fair share of the content budget.
2. Cover different roles before reading more files of one role.
3. Read at least two comparable implementations before declaring a repeated
   convention.
4. Follow imports, route registration, function calls, shared symbols, and
   corresponding tests from the selected files.
5. Record skipped modules and roles instead of describing a partial scan as
   complete.

## Cross-language cues

These are discovery cues, not mandatory architectures:

- **Python**: modules, decorators, Blueprint/route registration, Resource or
  handler classes, parsers, service/domain functions, database helpers, tests.
- **JavaScript / TypeScript / Vue / React**: pages, components, hooks, stores,
  routes, API clients, middleware, build scripts, unit and browser tests.
- **Java**: packages, annotations, controllers, DTOs, services, repositories,
  mappers, build files, integration and unit tests.
- **Go**: modules, packages, `cmd` entries, routers, handlers, services,
  repositories, middleware, table tests, and `go test` scopes.
- **CLI / SDK / library / data job**: command dispatch or public API, parsing,
  core operations, adapters, output boundary, fixtures, and invocation tests.
- **Unknown language**: use manifests, imports, callers, directory roles,
  configuration, examples, and tests. Do not invent framework semantics.

## Extracting rules

Architecture observations are intermediate evidence. Convert them into rules
about:

- placement and extension points;
- boundary-specific responsibilities;
- parameter and return contracts;
- stable naming, logging, error, and comment patterns;
- shared capability reuse;
- database and external integration entry points;
- shared change impact;
- real verification commands and working directories.

Reject a proposed rule when it only identifies a stack, restates a directory
tree, uses a quality slogan, lacks a project anchor, or cannot tell the new AI
what to do next.
