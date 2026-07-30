# Update example

This abbreviated example shows a semantic update after source changes.

## Request

**User**

> Update the generated rules after the recent backend changes. Preserve useful
> existing content and show me what actually changed.

## Read-only delta

**Agent**

> The existing Manifest and owned outputs validate. I followed the Git delta
> through the affected complete code chain: route → request validator →
> service → repository → service tests.
>
> Semantic rule delta
>
> | Rule | Classification | Evidence-backed reason |
> | --- | --- | --- |
> | Reuse the request schema helper | `added` | Three changed handlers now use the same helper and matching tests assert its errors. |
> | Open transactions in the service | `modified` | The repository no longer owns commit/rollback; both current write chains use the service transaction wrapper. |
> | Legacy direct insert recipe | `retired` | No supported caller remains. |
> | Read-only transaction handling | `conflict` | Two active services disagree, so it is excluded pending a correctness decision. |
>
> Unchanged frontend, naming, error-envelope, and test-placement rules are
> preserved without re-confirmation.
>
> Exact write plan
>
> - Replace the owned backend canonical rule and Manifest using current hashes.
> - Refresh selected adapters from the registry.
> - Leave unowned `CLAUDE.md` unchanged.
>
> May I write exactly this plan?

## Approval and validation

**User**

> Yes.

**Agent**

> Updated only the approved owned files. The full generated output tree
> validates. The read-only transaction conflict remains excluded and is
> reported for later resolution.
