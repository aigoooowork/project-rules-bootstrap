# `xm_bzhjswyh` content-first rule comparison

## Comparison method

The generated draft below was fixed before reading the project's existing
`RULES.md`, `AGENTS.md`, `CLAUDE.md`, or documentation. Those files were
excluded as discovery evidence. The draft uses current source, package
configuration, imports/callers, and tests only. Sensitive environment files
were existence-only.

This is a content check, not a scorecard. The question is whether a new AI can
use the generated rules to make a change that looks native to this repository.

## Blind code-derived draft

### Project and change-chain rules

1. **Trace a business change across both applications**
   - **Action:** before editing, identify the frontend page or shared workflow
     component, its function in `frontend/src/api/business.js`, the matching
     Flask resource in `backend/app/<domain>/res_<domain>.py`, the domain
     service, the `repository_ops.py` persistence call, and the nearest tests.
     Change every affected surface; do not infer a save path from the page
     alone.
   - **Scope:** preparation, reelection, adjustment, and assessment workflows.
   - **Project anchor:** preparation draft follows
     `PreparationCreateView.vue` → `savePreparationDraft` →
     `PreparationDraft.post` → `yw_preparation.service.save_application_draft`
     → `repository_ops.save_prep_application`.
   - **Verification:** run the nearest frontend `.test.mjs`, the matching
     backend pytest module, and the frontend build when Vue code changes.

2. **Treat shared workflow code as a multi-feature change**
   - **Action:** when changing `BusinessListPage.vue`,
     `ApplicationCreatePage.vue`, `NodeProcessView.vue`, shared detail helpers,
     attachment components, or `src/config/node-process.js`, enumerate all
     preparation/reelection/adjustment/assessment consumers and add
     changed-case plus non-affected-case checks.
   - **Scope:** shared frontend pages, field registries, helpers, and workflow
     components.
   - **Project anchor:** all four business modules import the common list,
     creation, detail, and node-process surfaces; focused tests also read or
     import those shared sources.
   - **Verification:** run every focused test that imports or statically reads
     the changed shared file, then run `npm run build` from `frontend`.

### Frontend rules

3. **Extend a feature through the existing common-page contract**
   - **Action:** keep thin feature views responsible for feature defaults,
     payload shaping, feature validation, and success navigation; reuse
     `ApplicationCreatePage.vue`, `BusinessListPage.vue`, `NodeProcessView.vue`,
     and detail components instead of cloning their layout or workflow.
   - **Scope:** new or changed Vue pages for the four business types.
   - **Project anchor:** `PreparationCreateView.vue`,
     `ReelectionCreateView.vue`, and `AssessmentReportCreateView.vue` configure
     `ApplicationCreatePage.vue`; the list views wrap `BusinessListPage.vue`.
   - **Verification:** exercise the feature-specific helper test and build the
     frontend.

4. **Put transport and response-shape behavior in the API layer**
   - **Action:** add endpoint wrappers to `frontend/src/api/business.js` and use
     the shared `http` instance. Reuse its token, fixed-parameter, signing,
     authentication-expiry, and network-error behavior. Validate the expected
     `code/data` shape with the existing `ensure*` helpers; keep views focused
     on UI state and user messages.
   - **Scope:** all frontend requests to project backend endpoints.
   - **Project anchor:** `business.js` consistently calls `http` and normalizes
     object/array/blob responses; `http.js` owns interceptors and signing.
   - **Verification:** run the HTTP-signing test, the nearest API/static test,
     and the frontend build.

5. **Keep local presentation fields out of backend payloads**
   - **Action:** mark display-only or locally edited fields with the existing
     `frontendOnly` convention or an explicit local key list, initialize them
     for rendering, and remove them when constructing save/submit payloads.
     Do not add backend fields merely to persist page-local presentation state.
   - **Scope:** node-process fields, creation forms, result/review presentation,
     and detail sections.
   - **Project anchor:** `src/config/node-process.js` declares
     `frontendOnly`; `NodeProcessView.vue` filters those fields; preparation
     creation uses `FRONTEND_ONLY_FIELD_KEYS` before payload construction.
   - **Verification:** run the focused `*-frontend-fields.test.mjs` or
     `*-frontend-only.test.mjs` test and inspect the final payload builder.

6. **Extract testable behavior from large Vue components**
   - **Action:** put reusable normalization, state transitions, visibility,
     payload building, and validation in adjacent `.mjs` helpers; import those
     helpers from the Vue component and test them directly with Node. Use
     source-reading static tests only for wiring that cannot be imported
     without a browser.
   - **Scope:** large common Vue components and feature workflows.
   - **Project anchor:** node-process, business-detail, assessment,
     preparation, and reelection behavior is split into adjacent `.mjs`
     modules with focused tests under `frontend/tests`.
   - **Verification:** run `node tests/<matching-test>.test.mjs` from
     `frontend`, then build when component wiring changes.

### Backend and API rules

7. **Add Flask endpoints through the domain registration chain**
   - **Action:** define request parsing in `backend/app/<domain>/parsers.py`,
     keep the `Resource` method as a thin adapter that loads the payload/user
     context/connection and calls the domain service, register it in
     `views_resource.py`, and preserve the domain blueprint prefix in
     `__init__.py`.
   - **Scope:** new and changed Flask REST endpoints.
   - **Project anchor:** preparation, reelection, adjustment, and assessment
     each repeat the `Blueprint` → `RES_LST` → `Resource` → service pattern.
   - **Verification:** import the app in testing mode to check route
     registration and run the service/resource tests for the endpoint.

8. **Keep business decisions in services and SQL mapping in repositories**
   - **Action:** implement validation, workflow branching, legacy/new payload
     normalization, and orchestration in `backend/yw_<domain>/service.py`.
     Put SQL, table names, row-to-API mapping, and insert/update mechanics in
     `repository_ops.py`. Pass the existing connection and user context through
     the chain rather than opening an unrelated database path.
   - **Scope:** backend domain behavior and persistence.
   - **Project anchor:** preparation and reelection services call their
     `repository_ops`; resource classes obtain `get_conn()` and delegate.
   - **Verification:** unit-test service behavior with repository functions
     monkeypatched, and test SQL/mapping separately with captured helper calls.

9. **Reuse project database helpers and map at the repository boundary**
   - **Action:** build parameters with the existing `sql_v2_*` helpers, use
     configured schema/table names, retain `is_deleted = 0` filtering where the
     comparable queries use it, and convert database `snake_case` rows to API
     `camelCase` dictionaries inside repositories. For partial saves, preserve
     omitted stored values with the local merge helper instead of replacing
     them with empty defaults.
   - **Scope:** GBase-facing repository queries and partial updates.
   - **Project anchor:** `yw_preparation/repository_ops.py` uses
     `sql_v2_build_sql_key`, `sql_v2_build_sql_in_params`, configured table
     constants, explicit row mapping, and `_payload_value`.
   - **Verification:** assert SQL fragments and bound parameter maps in
     repository tests; add a partial-update regression proving untouched fields
     remain unchanged.

10. **Route workflow actions through the existing executor**
    - **Action:** for submit/pass/reject/return/complete actions, call the
      existing domain service with `StateMachineExecutor` and update the
      configured transition path and affected side effects together. Do not
      duplicate status changes in a resource or frontend page.
    - **Scope:** business-order workflow transitions.
    - **Project anchor:** preparation resources construct
      `StateMachineExecutor`, while domain services orchestrate repository
      writes and workflow execution.
    - **Verification:** add service tests for the allowed transition, rejected
      transition, persisted side effects, and returned state.

### Startup and testing rules

11. **Preserve the backend startup chain**
    - **Action:** start from `backend/flask_run.py` (or the established manage
      entry) so environment setup occurs before importing the application.
      Register a new domain blueprint through `app.create_app()`'s existing
      blueprint list and middleware/error/runtime-service sequence.
    - **Scope:** backend startup, new domain modules, middleware, and deployment
      entry points.
    - **Project anchor:** `flask_run.py` calls `set_env()` before importing
      `manage.app`; `app/__init__.py` creates config, runtime services,
      blueprints, middleware, and error handlers in order.
    - **Verification:** import/create the app in testing mode and inspect its
      URL map without bypassing environment initialization.

12. **Match the repository's focused regression style**
    - **Action:** add the smallest regression next to the behavior: backend
      pytest tests monkeypatch service/repository boundaries and assert business
      outcomes or SQL; frontend Node tests import `.mjs` helpers or statically
      verify Vue wiring. Do not claim a Vue build proves behavior or visuals.
    - **Scope:** all code changes.
    - **Project anchor:** `backend/tests/test_preparation_member_profile.py`
      isolates repository/service collaborators; `frontend/tests` contains
      focused helper and wiring regressions.
    - **Verification:** run the exact new regression first, the relevant nearby
      suite second, and the frontend build for bundling when applicable.

## Blind-draft limits

- The first scanner pass respected existence-only sensitive paths but its
  fixed per-module sample favored alphabetically early package stubs and
  validation files. That finding led to a scanner change: it now ignores local
  worktree/tool caches, recognizes `.mjs/.cjs` tests, skips `__init__.py`, and
  prioritizes effective service, repository, route/resource, HTTP-client, and
  test anchors. Following imports and callers is still required because a
  bounded candidate list is not a call graph.
- Code alone did not establish every operational policy, required command,
  database compatibility exception, or intentionally restrictive prohibition.
  Such items should not be invented merely to make the rule set look complete.

## Comparison with the current human rules

The human rules were read only after the blind section was fixed.

| Area | Blind generated content | Current human rules | Assessment |
| --- | --- | --- | --- |
| End-to-end change chain | Gives a concrete Vue → API wrapper → Resource → service → repository → test recipe. | The chain exists across `RULES.md` and `backend/CLAUDE.md`, mostly as boundaries and navigation. | The generated version is more immediately usable for a coding task. |
| Shared frontend blast radius | Requires consumer enumeration and changed/non-affected checks, with common-component anchors. | `RULES.md` has an explicit shared-change impact rule. | Strong match; the generated version adds current source anchors. |
| Frontend implementation style | Captures thin feature pages, common page reuse, `.mjs` extraction, API normalization, and `frontendOnly` payload exclusion. | Root rules specify Vue/Element/Axios and portal behavior; `CLAUDE.md` records several frontend-only demo flows. | Generated content recovers day-to-day coding style that a stack list alone misses. Human rules remain richer for portal deployment facts. |
| Flask endpoint extension | Gives parser → registration → thin Resource → service instructions. | Human rules and backend navigation specify the same boundary and add template-conformance policy. | Strong match. The generated rule is safe because it is anchored in four repeated domains, not a generic Flask opinion. |
| Domain persistence | Keeps orchestration in current service functions and SQL/mapping in domain repositories. | `backend/CLAUDE.md` describes Resource → `yw_*` → workflow/query/repository; `RULES.md` warns against imposing a generic Service/Repository redesign. | Compatible when phrased as the observed current chain. The warning is important: generated wording must describe existing functions, not propose a new architecture. |
| Database behavior | Recovers configured table constants, parameter helpers, soft-delete filters, row mapping, and partial-update preservation. | Human rules add GBase 8s versions, Oracle mode, named-parameter prohibitions, loop/pagination/count rules, schema policy, and mandatory incremental SQL files. | Code-only discovery gets the implementation recipe but cannot reliably infer all operational and migration policy. Human content is materially richer here. |
| Startup | Recovers environment-first startup, application factory registration, and middleware setup. | Human rules define the exact environment, runtime versions, public-package injection, and frozen startup chain. | Strong structural match; human rules add external operational facts unavailable from ordinary source sampling. |
| Authentication/API transport | Recovers the single Axios client, signing/token injection, expiry handling, and `code/data` normalization. | Human rules add portal prefix, token-source, middleware normalization, and no-refresh policies. | Generated content is useful for ordinary endpoint work; human rules are necessary for deployment/auth correctness. |
| Tests | Gives backend monkeypatch boundary tests, frontend helper/static tests, and separates regression proof from build proof. | Human rules name key suites and execution discipline. | Generated style is concrete and evidence-led; human rules add authoritative acceptance scope. |
| Agent/process policy | Does not invent role, documentation, approval, fallback, or communication rules from source. | `AGENTS.md` defines quick execution, selective document loading, Chinese responses, and documentation synchronization. | Correctly absent from a blind code-derived draft. These are policy-only rules and should be merged from trusted human instructions in a normal run. |

### What the blind run recovered well

The new content contract recovered the parts that were missing from the former
output:

- exact code placement and reuse points;
- full frontend/backend/persistence/test chains;
- repeated local patterns rather than `Vue + Flask + black`;
- shared-code impact handling;
- project-specific payload, response, SQL-helper, and testing behavior;
- verification attached to every rule.

Nine of the twelve blind recipes substantially overlap current human guidance.
The remaining three are not filler: they expose implementation details that
are present in code but scattered or implicit in the human rule set.

### What code-only generation should not pretend to know

The blind run did not have enough evidence to publish these as authoritative:

- exact Python, Node, GSDK, and driver versions;
- the external `ch_apis_000` and `yw_utils` precedence policy;
- mandatory incremental SQL naming and delivery obligations;
- production portal paths and some token compatibility rules;
- documentation-loading and `CLAUDE.md` synchronization policy;
- intentionally restrictive “no fallback / no cross-boundary repair” rules.

These are good human rules. Normal Init should read and reconcile them as
trusted documentation evidence; they were excluded here only to test code
discovery independently.

### Drift and conflict the Update Skill should report

The current human set is richer, but it is not automatically identical to the
effective source:

- `RULES.md` describes a default middleware sequence containing
  `check_user/check_endpoint/check_limit/url_log`, while the current
  `app/__init__.py` registers
  `options/reqvals/check_token/authz/integrity/file_filter/timestamp`.
  `backend/CLAUDE.md` is closer to the current source. Update should classify
  this as a credible conflict, not silently copy either statement.
- The root rules caution against a generic Service/Repository redesign, while
  current domain code repeatedly uses function-based `service.py` and
  `repository_ops.py`. The correct generated rule must preserve the current
  concrete boundary without presenting it as a framework-wide architecture
  mandate.
- Some environment and dependency facts in human rules cannot be verified from
  package manifests alone. They should remain documented facts with their
  source, not be “re-discovered” from weak signals.

### Result

The revised Skills now generate a useful coding playbook instead of a project
profile. For this repository, the appropriate canonical output would emphasize
`project`, `frontend`, `backend`, `api`, `database`, `testing`, and narrowly
evidenced `restrictions`. A standalone architecture inventory is optional and
should not displace these actionable rules.

The safety workflow is also proportionate to the task: stable repeated code
style is accepted automatically, normal Init/Update uses one final write
confirmation, normal mode does not persist an audit file, and Update reports
only added/modified/retired/conflicting rule semantics.
