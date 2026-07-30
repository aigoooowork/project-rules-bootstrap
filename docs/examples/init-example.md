# Initialization example

This abbreviated example shows the normal content-first path. Discovery is
read-only and the user is asked once before files are written.

## Request

**User**

> Initialize AI project rules for this monorepo. I am new to it. Use Codex and
> Cursor and do not write until I confirm.

## Read-only discovery and content preview

**Agent**

> I traced three representative complete code chains instead of stopping at
> the package layout:
>
> - Web actions call feature API modules, which use the shared HTTP client;
>   response normalization stays in that client.
> - API handlers validate request shape, delegate business decisions to the
>   service layer, and use repository helpers for persistence.
> - Tests mirror the feature module and invoke the repository's checked-in test
>   command.
>
> Proposed actionable rules
>
> 1. **Add a web request**
>    - Action: place the endpoint wrapper in the feature API module and call the
>      shared HTTP client; do not create a second client.
>    - Scope: new and changed web requests under `apps/web/src`.
>    - Project anchor: `apps/web/src/api/orders.ts` and
>      `apps/web/src/http/client.ts` use this relationship.
>    - Verification: run the web unit command from the package manifest and the
>      nearest feature test.
> 2. **Change business persistence**
>    - Action: keep request parsing in the handler, business branching in the
>      service, and database calls in the existing repository helper.
>    - Scope: API changes under `services/api`.
>    - Project anchor: the create and update order chains both follow
>      handler → service → repository and reuse the transaction wrapper.
>    - Verification: run the matching service and repository tests.
>
> Unresolved and excluded: the two packages currently contain competing
> ownership claims for shared business logic, so no ownership constraint will
> be generated.
>
> Exact write plan
>
> - Create canonical project, frontend, backend, and testing rules.
> - Create the Manifest.
> - Create Codex and Cursor adapter files from the registry.
> - Leave all existing unowned files unchanged.
>
> May I write exactly this plan?

The agent does not ask for a role, language, or confirmation of the repeated
handler/service/repository convention. It uses the conversation language.

## Approval and validation

**User**

> Yes, write that plan.

**Agent**

> Wrote only the approved files. Canonical rules and adapter bindings validate.
> The unresolved ownership conflict remains excluded. No sensitive file body
> was read.
