# Confirmation policy

The normal path has one write confirmation after discovery, content preview,
conflict handling, and the exact file plan are complete. Discovery and preview
are read-only; do not create rule files before that approval.

Do not ask for the user's role. It does not improve code-style discovery.
Generate prose in the current conversation language unless the user explicitly
requests another language.

Promote stable repeated project patterns without confirmation. The repository
is the authority for local conventions, including consistent historical
choices that differ from generic best practice. Do not escalate formatting,
naming, file placement, reuse patterns, or verification commands when the
evidence threshold in the content contract is met.

## Strict-risk escalation

Pause before the final preview only when a decision can materially change
correctness or ownership:

- a credible conflict between current effective sources;
- a security or data correctness decision;
- a new strong constraint that is requested but not already established by
  project evidence;
- an unsafe or unowned overwrite;
- insufficient evidence where publishing a rule would mislead future coding.

Ask the smallest concrete question that resolves the risk. Show both choices,
their code anchors, affected scope, and practical consequence. Do not escalate
generic best practice, personal taste, framework defaults, or a stable legacy
pattern merely because a cleaner design exists.

When a strong constraint is explicitly approved, record its scope, reason,
exception policy, verification, and a unique confirmation ID. In update mode,
preserve a validated unchanged constraint without re-confirmation. A changed
scope, action, exception, verification, or strength is a new decision.

If a risk remains unresolved, exclude it from canonical rules and continue
with unaffected content when safe. Normal operation does not require a
persistent analysis file. Strict-risk mode may propose
`.ai/rules.analysis.md`, but it is included in the same exact final write plan
and the same one write confirmation.
