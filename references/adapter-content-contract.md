# Adapter content contract

Adapters are vendor-facing entry points, not another rule source. They may only locate `.ai/rules/`, route a task to relevant canonical domains, declare supported scope/loading metadata, and state the registry support mode.

Adapters never change canonical semantics, invent constraints, duplicate the complete canonical rule set, present a future design as a fact, or mix another vendor's syntax. Generate only the selected adapter files and keep routing concise. The authoritative path, template, support claim, verification date, and source are in `references/adapters.json`; adapter output and manifest metadata must match it exactly.

When multiple registry entries use one shared static template, that body is identity-neutral and contains no `adapter-id`, support, scope, or loading declaration. The renderer removes the template metadata comment and prepends those four declarations from the selected, validated registry entry. This is rendering metadata, not a template marker; the shared body is never edited to name a particular tool.
