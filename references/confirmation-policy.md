# Confirmation policy

Discovery, questions, and preview are read-only. After content is settled,
request one final write confirmation for the exact file plan.

Stable repeated project conventions do not need a separate question. Ask only
when a credible conflict, security/data-correctness choice, weak evidence, or
unsafe ownership decision would materially change the result. Ask one to three
focused questions at a time and normally no more than five to ten total. Show
the competing code anchors, affected scope, and practical consequence.

Strong constraints are a separate decision before the final write approval.
Detect candidates from both wording and meaning. Candidate wording includes
`MUST`, `NEVER`, `SHALL`, `REQUIRED`, `DO NOT`, `ONLY`, `ALWAYS`, `必须`,
`禁止`, `不得`, `严禁`, `不允许`, `只能`, `仅允许`, `务必`, and `不能`.
Also treat wording without these tokens as strong when it creates a prohibition,
mandatory action, approval prerequisite, or only-allowed path. Do not promote a
type signature or directly observed limitation merely because its description
contains a candidate token.

For each new or changed strong instruction, show the exact text, scope, reason,
exception policy, project evidence, and verification; include it only after
explicit confirmation. Preserve an unchanged validated confirmation during
Update. Any semantic change requires a new decision.

Every question follows this shape: observed project anchors; the unresolved
choice; the candidate rule affected; concrete choices and their consequences.
Do not ask a generic policy questionnaire when repository evidence can make the
question specific.

Exclude unresolved claims and continue with unaffected content when safe.
Never persist analysis notes or `.ai/rules.analysis.md`; the reviewed canonical
rules and v2 manifest are the only generated state.
