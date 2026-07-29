# Output schema

The generated Manifest is UTF-8 JSON at `.ai/rules-manifest.json`. This Draft 2020-12 JSON Schema is normative. `additionalProperties: false` means a property not listed below is forbidden; a field absent from `required` is optional. Timestamps are ISO-8601 strings. The renderer must replace the empty structural template with values satisfying this schema before writing it.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "project", "scan_baseline", "rules", "adapters", "confirmations"],
  "properties": {
    "version": {"type": "string", "const": "1.0"},
    "project": {
      "type": "object", "additionalProperties": false,
      "required": ["name", "language"],
      "properties": {
        "name": {"type": "string", "minLength": 1, "description": "Non-identifying display name only."},
        "language": {"type": "string", "enum": ["en", "zh-CN"]}
      }
    },
    "scan_baseline": {
      "type": "object", "additionalProperties": false,
      "required": ["kind", "captured_at", "paths"],
      "properties": {
        "kind": {"type": "string", "enum": ["git", "full-scan"]},
        "captured_at": {"type": "string", "format": "date-time"},
        "paths": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "head": {"type": ["string", "null"]},
        "fallback_reason": {"type": ["string", "null"]}
      }
    },
    "analysis_ownership": {"$ref": "#/$defs/analysisOwnership"},
    "rules": {"type": "array", "items": {"$ref": "#/$defs/rule"}},
    "adapters": {"type": "array", "items": {"$ref": "#/$defs/adapter"}},
    "confirmations": {"type": "array", "items": {"$ref": "#/$defs/confirmation"}}
  },
  "$defs": {
    "analysisOwnership": {
      "type": "object", "additionalProperties": false,
      "required": ["version", "owner", "path", "sha256"],
      "properties": {
        "version": {"type": "string", "const": "1.0"},
        "owner": {"type": "string", "const": "project-rules-bootstrap"},
        "path": {"type": "string", "const": ".ai/rules.analysis.md"},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
      }
    },
    "rule": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "domain", "type", "status", "scope", "text", "confidence", "evidence"],
      "properties": {
        "id": {"type": "string", "pattern": "^(project|architecture|coding-style|frontend|backend|api|database|testing|security|restrictions)(\\.[a-z0-9][a-z0-9._-]*)+$"},
        "domain": {"type": "string", "enum": ["project", "architecture", "coding-style", "frontend", "backend", "api", "database", "testing", "security", "restrictions"]},
        "type": {"type": "string", "enum": ["fact", "convention", "constraint"]},
        "status": {"type": "string", "enum": ["confirmed", "candidate", "unknown", "conflict", "stale"]},
        "scope": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/evidence"}},
        "confirmation_id": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
        "exception_policy": {"type": "string", "minLength": 1},
        "verification": {"type": "string", "minLength": 1},
        "stale": {"type": "boolean"},
        "supersedes": {"type": "string", "minLength": 1}
      },
      "allOf": [
        {
          "if": {"properties": {"type": {"const": "constraint"}}},
          "then": {"required": ["confirmation_id", "reason", "exception_policy", "verification"]}
        }
      ]
    },
    "evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["kind", "location", "observation", "captured_at"],
      "properties": {
        "kind": {"type": "string", "enum": ["source", "configuration", "documentation", "git", "user-confirmation"]},
        "location": {"type": "string", "minLength": 1},
        "observation": {"type": "string", "minLength": 1},
        "captured_at": {"type": "string", "format": "date-time"},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
        "commit": {"type": "string", "minLength": 1}
      }
    },
    "confirmation": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "recorded_at", "decision", "scope", "rule_ids"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "recorded_at": {"type": "string", "format": "date-time"},
        "decision": {"type": "string", "enum": ["confirmed", "rejected", "deferred"]},
        "scope": {"type": "string", "minLength": 1},
        "rule_ids": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
        "batch_reason": {"type": "string", "minLength": 1}
      }
    },
    "adapter": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "path", "support", "template", "registry_version", "scope_loading", "import_capability", "consumers"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "path": {"type": "string", "minLength": 1},
        "support": {"type": "string", "enum": ["native-auto", "import-supported", "manual-reference", "unverified"]},
        "template": {"type": "string", "minLength": 1},
        "registry_version": {"type": "string", "minLength": 1},
        "scope_loading": {"type": "string", "minLength": 1},
        "import_capability": {"type": "string", "minLength": 1},
        "consumers": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string", "minLength": 1}}
      }
    }
  }
}
```

`assets/templates/rules-manifest.json` is a pre-render structural template and
therefore uses `scan_baseline: null` and `analysis_ownership: null`; that
template is not a valid final Manifest. The renderer must replace every
placeholder and the null baseline before validation. It must also replace the
ownership placeholder with the strict object above when
`.ai/rules.analysis.md` exists, or remove the property when it does not.

The validator additionally enforces invariants that JSON Schema cannot express
directly: rule IDs, confirmation-record IDs, constraint `confirmation_id`
values, and adapter owner IDs are unique; every Manifest rule has exactly one
canonical `rule-id` marker on its own line bound to its immediately following
single list-item body; inline and heading-embedded markers are unbound
occurrences and invalid; the body matches Manifest `rule.text` after trimming
and collapsing Unicode whitespace without changing case or punctuation;
semantic canonical sections are not duplicated; and mandatory `MUST`, `NEVER`,
`必须`, or `禁止` instructions are detected in both headings and bodies and
occur only as marker-bound items in the explicit confirmed-constraints
section.
Adapter metadata matches the authoritative registry. Every constraint in any
canonical rule file has its own confirmed record whose ID, sole rule
membership, and scope match. A
constraint also requires linked `user-confirmation` evidence, reason, exception
policy, and verification. A shared adapter output has one owner record and
lists every selected consumer in `consumers`.

When `.ai/rules.analysis.md` exists, the Manifest must contain
`analysis_ownership` with the fixed version, owner, and path above plus the
lowercase SHA-256 of the exact file bytes. If the analysis is absent, the
property must be absent. The validator rejects missing, stale, malformed, or
orphaned ownership records.

`project.name` and all confirmation records must contain no person name, email,
account identifier, or Git identity. Evidence records may identify local paths
and bounded commit identifiers, but never secret content. Stale rules must set
`stale: true`.

## Write-plan preconditions

The two write gates use a separate operational plan enforced by
`scripts/write_outputs.py`:

| Mode | Target state | Required precondition |
| --- | --- | --- |
| `create` | Path is absent and not symlinked. | No prior hash is allowed. |
| `replace-owned` | Existing regular file is proven to belong to the validated prior output tree. | Exact pre-update SHA-256; Gate 2 also validates the prior Manifest and canonical/adapter ownership. |
| `managed-block` | Existing regular UTF-8 file contains exactly one ordered managed-marker pair. | Exact pre-update file SHA-256; on update, the validated prior Manifest must authorize the adapter path; on initialization, the validated new Manifest and authoritative registry must authorize it. |

Gate 1 permits only `.ai/rules.analysis.md`; updating it requires the complete
prior output tree to validate and the exact prior Manifest snapshot to contain
an `analysis_ownership` record whose SHA-256 matches both the existing file and
the caller's pre-update hash. The caller hash is only a concurrency
precondition and cannot self-authorize ownership. An older Manifest without
this ledger must be migrated through an explicit ownership re-confirmation
before replacement. Gate 2 must not write the analysis path and must write or
retain a final Manifest ledger matching the Gate 1 analysis bytes. The writer
retains the analysis parent and file handles through Gate 2, rechecks the same
file handle and its namespace identity immediately before installing the
Manifest, and installs the Manifest last. Gate 2 also
rejects an existing Manifest or canonical file unless the prior output tree
validates before any write. Missing provenance is never permissive for managed
blocks. Canonical roots and candidates are rejected before reading when they
are linked, reparse-point, sensitive, or outside the target root.

Every approved payload is staged in a same-directory temporary file before
commit. Validation, staging, claim, install, rollback, and cleanup use retained
directory handles and handle-relative no-follow operations. POSIX uses
`dir_fd` plus `O_NOFOLLOW`; Windows uses native `RootDirectory`
handle-relative operations. POSIX must provide every required no-follow and
directory flag plus the required handle-relative open, stat, scan, rename,
link, unlink, and directory operations; a missing capability fails closed
instead of degrading to path-based or follow-link behavior. Portable paths and
handle-relative child names reject `:` to exclude Windows alternate data
streams. Existing targets are atomically claimed and then checked for the
prepared identity and hash without following links. If any commit step fails,
all replacements are restored and all newly created targets are removed. If
rollback itself fails, the unrecovered backup is preserved and a root-level
`.project-rules-bootstrap-recovery-*.json` journal records only recovery paths,
states, expected hashes, and error types—never file contents.
The commit point is the successful installation of every planned output. A
subsequent backup-cleanup failure is recoverable housekeeping: the committed
output remains successful, the cleanup artifact is retained, all handles are
closed, and a content-free `.project-rules-bootstrap-cleanup-*.json` journal
plus warning records the remaining path and error type.
Managed-block replacement operates on bytes, preserves an existing UTF-8 BOM
and LF/CRLF convention, and leaves the prefix through the start marker and the
suffix beginning at the end marker byte-for-byte unchanged.
