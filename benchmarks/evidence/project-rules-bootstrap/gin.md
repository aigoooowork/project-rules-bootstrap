# Gin — HTTP routing

## Scope
Route registration and request dispatch in the root Gin package.

## Confirmed facts
- `RouterGroup.GET()`, `POST()`, and `Handle()` in `routergroup.go` combine group middleware and delegate registration to `Engine.addRoute()`.
- `Engine.addRoute()` in `gin.go` stores the handler chain in the routing tree implemented by `tree.go`.
- `Engine.handleHTTPRequest()` resolves a route, assigns its handlers to `Context`, and executes the chain; `Context.Next()` in `context.go` advances through middleware and the terminal handler.
- Root behavior tests include `routes_test.go`, `routergroup_test.go`, `middleware_test.go`, and `context_test.go`.

## Execution rules
- Trace route changes as `RouterGroup.Handle()` → `Engine.addRoute()` → `Engine.handleHTTPRequest()` → `Context.Next()`; include `tree.go`, middleware order, and abort behavior when relevant.
- Put focused tests beside the owning root file; use `binding/` and `render/` tests only when the request binding or response renderer boundary changes.
- Preserve the distinction between registration-time path validation and request-time lookup/error behavior.

## Verification
- Focused: `go test ./ -run '^TestRouterGroupRouteOK$'`
- Formatting check: `make fmt-check`
- Repository suite: `make test`

## Related rules
No additional canonical group is needed for this benchmark task.
