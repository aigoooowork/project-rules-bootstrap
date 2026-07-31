# FastAPI — request routing

## Scope
HTTP route registration, dependency solving, endpoint execution, and response serialization in `fastapi/`.

## Confirmed facts
- `FastAPI.add_api_route()` in `fastapi/applications.py` delegates route construction to the router.
- `APIRouter.add_api_route()` and `APIRoute.get_route_handler()` are in `fastapi/routing.py`.
- The request handler in `fastapi/routing.py` calls `solve_dependencies()` from `fastapi/dependencies/utils.py`, then `run_endpoint_function()`, then `serialize_response()`.
- Product tests live under `tests/`; runnable project gates are encoded in `scripts/test.sh` and `pyproject.toml`.

## Execution rules
- For a request-lifecycle change, trace `add_api_route()` → `get_route_handler()` → `solve_dependencies()` → `run_endpoint_function()` → `serialize_response()` and place the change at the narrowest owning link.
- Add a regression under the existing `tests/test_*.py` area that exercises the public FastAPI API; use `docs_src/` only for documentation examples, not as the product implementation.
- When changing dependency injection, cover both the dependency graph result and cleanup/error behavior around the route handler.

## Verification
- Focused: `pytest tests/test_route_scope.py -q`
- Lint/format configuration: `ruff check fastapi tests` and `ruff format --check fastapi tests`
- Full suite entry point: `bash scripts/test.sh`

## Related rules
No additional canonical group is needed for this benchmark task.
