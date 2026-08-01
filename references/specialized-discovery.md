# Conditional specialized discovery

Read only the specialties listed in `project_evidence.specialized_discovery`.
A dependency name or path is a routing hint; verify the real source chain before
creating a rule. Specialty analysis may enrich any dynamic group and never
forces a fixed file.

Development and test-extra dependencies do not establish a project type.
Runtime signals may come from Python, Node, Go, Java, Rust, or another supported
dependency manifest.

## API

Trace route registration, request/parameter parsing, dependency or permission
resolution, business handling, response serialization, exception conversion,
schema/OpenAPI generation, and focused public-API tests.

## Database

Trace model/schema declarations, repository/DAO/query construction, transaction
ownership, migrations, update/delete behavior, callers, and database-focused
tests. Current migrations do not establish future compatibility policy.

## Frontend

Trace router/page entry, component composition, state ownership, API client,
form validation, permission behavior, build configuration, and user-visible
tests. Prefer product source over story/demo/example code.

## AI

Trace model-client entry, model selection/routing, prompt storage/loading,
streaming/retry/timeout handling, RAG chunk/embed/retrieve/rerank/citation flow,
agent tool registration/argument/result handling, evaluation data and commands,
fallbacks, and error handling. Code can prove the current chain; model-change
authority, cost limits, data policy, and acceptance thresholds require user
confirmation when they affect rules.
