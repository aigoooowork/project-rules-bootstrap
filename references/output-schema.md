# Output schema

The generated Manifest is `.ai/rules-manifest.json`, encoded as UTF-8 JSON.

| Field | Required | Shape and meaning |
| --- | --- | --- |
| `version` | yes | Schema version string. |
| `project` | yes | Object with non-identifying project display name and selected output language. |
| `scan_baseline` | yes | Object: `kind` (`git` or `full-scan`), `captured_at`, optional local `head`, bounded `paths`, and fallback reason when applicable. |
| `rules` | yes | Array of rule records. |
| `adapters` | yes | Array of selected adapter records matching the authoritative registry. |
| `confirmations` | yes | Array of non-identifying confirmation records. |

A rule record has `id`, `domain`, `type`, `status`, `scope`, `text`, `confidence`, `evidence`, and optional `confirmation_id`, `stale`, and `supersedes`. Rule IDs are lowercase dot-separated identifiers beginning with their domain (for example, `backend.repository-access`); each ID appears in one canonical domain file only. `domain` is one of `project`, `architecture`, `coding-style`, `frontend`, `backend`, `api`, `database`, `testing`, `security`, or `restrictions`. `type` is `fact`, `convention`, or `constraint`; `status` is `confirmed`, `candidate`, `unknown`, `conflict`, or `stale`; `confidence` is exactly `high`, `medium`, or `low`.

Each evidence record has `kind`, `location`, `observation`, and `captured_at`; it may include a bounded line range or local commit identifier, but never secret content. A confirmation record has `id`, `recorded_at`, `decision`, `scope`, `rule_ids`, and optional `batch_reason`; it contains no name, email, user ID, or Git identity. An adapter record has `id`, `path`, `support`, `template`, and `registry_version`; optional scope/loading fields must preserve the registry meaning.
