# React Hook Form — form submission

## Scope
Form-control behavior under `src/`, especially validation and submit handling.

## Confirmed facts
- `useForm()` in `src/useForm.ts` creates or adopts a form control and subscribes React state to that control.
- The concrete control is built by `createFormControl()` in `src/logic/createFormControl.ts`.
- Submission flows through `handleSubmit` in that file, which invokes resolver or `executeBuiltInValidation()` before dispatching the valid/invalid callback and form-state updates.
- Behavior tests for the hook live in `src/__tests__/useForm.test.tsx`; compile-only public type cases live below `src/__typetest__/`.

## Execution rules
- Trace submit changes as `useForm()` → `createFormControl()` → `handleSubmit()` → `executeBuiltInValidation()`; do not treat the example app under `app/` as the implementation.
- Add the regression at the narrowest existing `useForm` or logic test, and add a type case when overloads, generics, or public return types change.
- Check `src/index.ts` and the rollup export assertions when adding or moving a public symbol.

## Verification
- Focused behavior: `pnpm test -- src/__tests__/useForm.test.tsx`
- Static types: `pnpm type` and, for type fixtures, `pnpm test:type`
- Public bundle/export path: `pnpm build`

## Related rules
No additional canonical group is needed for this benchmark task.
