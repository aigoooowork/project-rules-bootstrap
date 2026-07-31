# Contributing

Preserve the central contract: `.ai/rules/` is the only semantic source,
repository evidence and explicit strong-constraint decisions determine its
content, and adapters only route tools to `.ai/rules/index.md`.

## Test

```text
python -m unittest discover -s tests -v
```

Review the behavior scenarios in `evals/evals.json` and keep every fixture
unchanged before final write approval.

## Adapter changes

An adapter change updates one exact record in `references/adapters.json` with
`id`, `name`, unique output `path`, `support`, and `template`. Verify the path
and loading behavior from current vendor documentation. Add or update the
smallest routing-only template and its tests, then update both READMEs and
`docs/compatibility.md`.

Adapters may not copy canonical rules, invent constraints, embed registry
metadata comments, share one multi-consumer output, or overwrite an unowned
file. Unknown tools remain unsupported instead of receiving a guessed path.

## Pull requests

Keep local benchmark checkouts, generated caches, evaluation outputs, and
planning workspaces out of commits. Report the exact tests and benchmark pins
used, plus any unverified modules or compatibility claims.
