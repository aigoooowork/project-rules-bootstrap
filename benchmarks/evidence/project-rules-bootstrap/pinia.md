# Pinia — store lifecycle

## Scope
Changes to the public Pinia store API and runtime under `packages/pinia/src/`.

## Confirmed facts
- `packages/pinia/src/index.ts` exports the package API.
- `createPinia()` in `packages/pinia/src/createPinia.ts` builds the plugin container and activates it during installation.
- `defineStore()` in `packages/pinia/src/store.ts` selects `createSetupStore()` or `createOptionsStore()`; both converge on the store setup and active-Pinia state in the same file.
- Runtime behavior tests are colocated in `packages/pinia/__tests__/`; public type contracts are also exercised by the repository's `test:types` and `test:dts` scripts.

## Execution rules
- For a store-runtime change, trace `defineStore()` → `createSetupStore()` / `createOptionsStore()` → `setActivePinia()` across `packages/pinia/src/store.ts` and `packages/pinia/src/rootStore.ts`; start from the public export in `packages/pinia/src/index.ts`.
- Keep a behavioral regression test beside the existing runtime tests and a type test when the public generic/API shape changes.
- Treat `packages/nuxt`, `packages/testing`, and `packages/docs` as downstream consumers; inspect them only when the changed export or behavior crosses those package boundaries.

## Verification
- Focused runtime: `pnpm test:vitest run packages/pinia/__tests__/store.spec.ts`
- Types: `pnpm test:types`
- Full repository gate: `pnpm test`

## Related rules
No additional canonical group is needed for this benchmark task.
