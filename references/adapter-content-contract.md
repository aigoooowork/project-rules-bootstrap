# Adapter content contract

## Read-only preview before Gate 1

Read the selected assistants from `adapters.json` before Gate 1 and show one
preview row per selected assistant. Each row contains the adapter ID and name,
the exact registry output path, and the registry support mode. The supported
preview values are `native-auto`, `import-supported`, `manual-reference`, and
`unverified`.

The preview is a plan, not a write. Gate 1 blocks creation or modification of
the analysis file; it does not hide already verified adapter metadata.

- CodeBuddy: `native-auto` at `.codebuddy/rules/<rule>/RULE.mdc`.
- WorkBuddy: `manual-reference` at the root `RULES.md`; tell the user to import
  or `@` reference that file, and do not claim a native WorkBuddy rules path.
- Missing registry entry or a registry support value of `unverified`: report the assistant separately as unverified,
  invent no path or support mode, and generate no adapter.

Adapters are vendor-facing entry points, not another rule source. They may only locate `.ai/rules/`, route a task to relevant canonical domains, declare supported scope/loading metadata, and state the registry support mode.

Adapters never change canonical semantics, invent constraints, duplicate the complete canonical rule set, present a future design as a fact, or mix another vendor's syntax. Generate only the selected adapter files and keep routing concise. Before reading or writing an adapter path, resolve its identity from the trusted registry and validate the registry version, ID, path, template, scope/loading, import mode, support, and selected consumers. Reject absolute paths, parent traversal, sensitive names, symlinks, and paths outside the target root. Manifest-provided paths never authorize discovery. The authoritative path, template, support claim, verification date, and source are in `references/adapters.json`; adapter output and manifest metadata must match them exactly.

When multiple registry entries use one shared output, each entry declares the
same `shared_output` key and a unique `selection_priority`. Resolve that group
once. The highest-priority selected concrete consumer owns the file; the
single Manifest adapter record lists every selected member in `consumers`.
For WorkBuddy plus Generic, WorkBuddy owns one root `RULES.md` and the
consumers are `generic` and `workbuddy`.

A shared static template body is identity-neutral and contains no
`adapter-id`, support, scope, loading, or consumers declaration. The renderer
removes template metadata and prepends the selected, validated owner's five
declarations. This is rendering metadata, not a template marker; the shared
body is never edited to name a particular tool.

When an adapter path is a user-maintained file, update only the explicit bytes
between exactly one
`<!-- project-rules-bootstrap:start -->` /
`<!-- project-rules-bootstrap:end -->` pair. The approved write plan includes
the exact current file SHA-256. On an update run, the validated prior Manifest
must authorize that adapter path. On an initialization run, the validated new
Manifest must match an authoritative, non-`unverified` registry entry for the
exact adapter path and selected consumers. Missing ownership provenance never
authorizes a managed block. Preserve any UTF-8 BOM, the existing LF or CRLF
convention, both markers, and every byte outside them. Reject missing,
duplicate, nested, reversed, symlinked, unowned, or hash-mismatched targets;
never fall back to whole-file replacement.
