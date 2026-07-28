# Fixture backend

## Scope
src/api/**

## Confirmed facts
- API handlers currently delegate persistence to repositories.

## Confirmed constraints
<!-- rule-id: backend.repository-boundary -->
- API handlers must not access the database directly.

## Execution rules
- Keep database access behind repositories.

## Verification
- Inspect changed handlers for direct database access.

## Related rules
- None.
