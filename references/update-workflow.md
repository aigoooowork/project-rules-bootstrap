# Update workflow

1. Validate the prior v2 manifest and every owned file hash.
2. Compute a local Git delta when reliable; otherwise perform a bounded scan
   and name omitted or unverified areas.
3. Read changed bodies and trace every affected complete code chain upstream,
   downstream, through persistence/integration, returned state, consumers, and
   tests. A filename change alone is not a rule change.
4. Compare code evidence with existing actionable recipes. Preserve unchanged
   rules without re-confirmation; remove or revise a rule when its real anchor,
   boundary behavior, or verification no longer exists.
5. Present a semantic delta:

| Classification | Meaning |
| --- | --- |
| `added` | Current evidence establishes a new actionable recipe. |
| `modified` | The same task now follows a different real chain or contract. |
| `retired` | The supported entry or implementation chain no longer exists; remove its exact previously owned output. |
| `conflict` | Credible current sources disagree; exclude until resolved. |

6. Apply the confirmation policy. Preserve unchanged confirmation records;
   explicitly confirm every new or semantically changed strong constraint.
7. Preview `create`, `replace-owned`, `delete-owned`, unchanged, and
   `manual-only` paths. Replacement and deletion require ownership in the
   on-disk prior manifest and the exact current SHA-256. Every prior owned path
   omitted from the next manifest requires one `delete-owned` entry.
8. After one final write approval, preflight the entire plan, write each file
   atomically, install the manifest last, and validate the result.

Formatting-only changes do not create semantic delta entries. First imports
from human-authored AI rules are evidence candidates, not trusted constraints.
