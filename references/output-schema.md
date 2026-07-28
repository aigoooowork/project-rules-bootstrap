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
    "rules": {"type": "array", "items": {"$ref": "#/$defs/rule"}},
    "adapters": {"type": "array", "items": {"$ref": "#/$defs/adapter"}},
    "confirmations": {"type": "array", "items": {"$ref": "#/$defs/confirmation"}}
  },
  "$defs": {
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
therefore uses `scan_baseline: null`; that template is not a valid final
Manifest. The renderer must replace every placeholder and the null baseline
before validation.

The validator additionally enforces invariants that JSON Schema cannot express
directly: rule IDs, confirmation-record IDs, constraint `confirmation_id`
values, and adapter owner IDs are unique; every Manifest rule has exactly one
canonical `rule-id` marker; adapter metadata matches the authoritative
registry; and every constraint in any canonical rule file has a confirmed
record whose ID, rule membership, and scope match. A
constraint also requires linked `user-confirmation` evidence, reason, exception
policy, and verification. A shared adapter output has one owner record and
lists every selected consumer in `consumers`.

`project.name` and all confirmation records must contain no person name, email,
account identifier, or Git identity. Evidence records may identify local paths
and bounded commit identifiers, but never secret content. Stale rules must set
`stale: true`.
