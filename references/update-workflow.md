# Update workflow

1. Validate the complete prior Manifest and generated output tree. Capture the
   exact current SHA-256 for every proposed existing-file write.
2. Compute a local Git delta when available. If no reliable baseline exists,
   run a bounded full scan and name truncated or unverified areas.
3. Read changed bodies and trace each affected complete code chain upstream,
   downstream, through persistence or integration, and into tests. A changed
   filename alone is not a rule change.
4. Compare current stable patterns with existing actionable rules. Preserve an
   unchanged rule without re-confirmation. Reconsider it only when the stable
   code pattern changed or the previous evidence no longer exists.
   In short: preserve it without re-confirmation unless the stable code pattern changed.
5. Present a semantic rule delta:

| Rule | Classification | Evidence-backed reason |
| --- | --- | --- |
| New repository call recipe | `added` | A repeated current code chain establishes it. |
| Existing validation recipe | `modified` | Current callers and tests now use another shared helper. |
| Removed legacy integration | `retired` | No current call chain or supported entry point remains. |
| Competing transaction behavior | `conflict` | Current effective paths disagree; exclude until resolved. |

6. Separately classify proposed writes as `create`, `replace-owned`,
   `managed-block`, or `manual-only`. Never overwrite an unowned file
   wholesale. Reject symlinks, hash mismatches, invalid markers, and paths
   outside the exact plan.
7. Apply the confirmation policy. Request one write confirmation for the exact
   final plan, then stage the approved set, commit it transactionally, install
   the Manifest last, and validate the complete output tree.

Formatting-only changes do not create semantic rule delta entries. First
imports from human-authored rules are evidence candidates, not automatically
trusted constraints. Unchanged validated constraints keep their existing
confirmation record; semantic changes follow strict-risk handling.
