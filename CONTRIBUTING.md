# Contributing

Contributions should preserve the central contract: `.ai/rules/` is the only
canonical semantic source, evidence and user confirmation determine its
content, and adapters only route tools to that content.

## Set up and test

The repository uses the Python standard library for its current unit and
contract tests:

```text
python -m unittest discover -s tests -v
```

Run the complete suite before and after a change. Behavior scenarios live in
`evals/evals.json`; this repository does not bundle a behavior-eval runner. Use
the Skill-evaluation workflow available in your agent environment, or manually
review every prompt and expectation. At each pre-approval gate stop, verify
that the fixture tree has not changed; after approval, verify that writes stay
within the exact approved scope.

## Add or update an adapter

An adapter change is one coherent compatibility change. Update all of the
following:

1. **Registry entry:** add or edit one object in `references/adapters.json`.
   Supply the exact `id`, display `name`, output `path`, `scope_loading`,
   `import_capability`, compatibility `support`, template path, ISO verification
   date, and official `sources`.
   If two entries intentionally share one output path, give both the same
   `shared_output` key and distinct integer `selection_priority` values. Their
   path, template, support, scope/loading, and import metadata must be identical.
2. **Template:** add the smallest suitable file under
   `assets/templates/adapters/`, or reuse an identity-neutral shared template.
   The rendered adapter may locate `.ai/rules/`, route relevant domains, and
   state registry metadata. It must not copy canonical rules or introduce a new
   rule.
3. **Official source:** use the tool vendor's current documentation. Verify the
   exact path and loading behavior. Do not promote forum inference, a stale
   example, or an unverified path to `native-auto`.
4. **Unit test:** extend the registry/render/validation tests under `tests/`.
   Assert the adapter ID, exact path, support level, scope/loading metadata,
   template, selected consumers, shared-output resolution, and rejection of
   mismatched or unsafe claims.
5. **Behavior eval:** add or update a focused scenario in `evals/evals.json`.
   Check the read-only preview, both write gates, selected-only generation, and
   any required manual action.
6. **Public documentation:** update both READMEs and
   `docs/compatibility.md`, keeping identifiers, paths, levels, verification
   dates, and source URLs identical to the registry.

Use one of the schema compatibility levels:

- `native-auto`
- `import-supported`
- `manual-reference`
- `unverified`

The active adapter registry may use only a subset. If evidence does not verify
a loading path, keep the tool unverified: invent no path and generate no
adapter. A `manual-reference` entry must tell the user exactly how to import or
reference the file and must never be described as automatic.

Registry and Manifest adapter paths must be portable relative paths. Reject
absolute paths, parent traversal, sensitive names, symlinks, and targets
outside the output root. The validator resolves identity from the trusted
registry before it discovers or reads any adapter output.

## Preserve canonical rule semantics

Adapter and documentation work must not change:

- evidence classification or confidence;
- rule scope, action, exception, or verification;
- confirmation records or the strength of a constraint;
- the two write gates;
- conflict handling or ownership boundaries;
- the sensitive-file and outside-root safety boundary.

If the contribution intentionally changes any of those behaviors, treat it as
a separate canonical-semantics proposal with dedicated design review, tests,
and behavior evals. Do not hide that change inside an adapter template,
compatibility update, or documentation patch.

## Documentation checks

Before submitting:

1. Parse `references/adapters.json`.
2. Compare every documented adapter ID, exact path, compatibility level, and
   verification date with the registry.
3. Check that every published official-source URL is present in the matching
   registry entry.
4. Search for `manual-reference` and confirm each occurrence describes an
   explicit action rather than auto-loading.
5. Run the unit suite and review Markdown links.

Keep the Chinese README natural and reviewable. Do not translate filenames,
adapter IDs, code paths, or compatibility-level identifiers.

## Pull request scope

Keep generated caches, local evaluation output, and SDD workspaces out of the
commit. Explain which compatibility facts were verified, which tests ran, and
what remains `unverified`.
