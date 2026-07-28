# Adapter content contract

Adapters are vendor-facing entry points, not another rule source. They may only locate `.ai/rules/`, route a task to relevant canonical domains, declare supported scope/loading metadata, and state the registry support mode.

Adapters never change canonical semantics, invent constraints, duplicate the complete canonical rule set, present a future design as a fact, or mix another vendor's syntax. Generate only the selected adapter files and keep routing concise. The authoritative path, template, support claim, verification date, and source are in `references/adapters.json`; adapter output and manifest metadata must match it exactly.
