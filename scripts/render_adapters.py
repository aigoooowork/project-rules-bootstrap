"""Load and render small, unique per-tool canonical rule adapters."""

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Tuple


REGISTRY_FIELDS = {"version", "adapters"}
ADAPTER_FIELDS = {"id", "name", "path", "support", "template"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class RenderedAdapter:
    path: str
    content: str


def _safe_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("{} must be a safe relative path".format(label))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("{} must be a safe relative path".format(label))
    return path.as_posix()


def validate_adapter_registry_data(data: object) -> Dict[str, object]:
    """Validate the v2 registry and return a detached copy."""
    if not isinstance(data, dict) or set(data) != REGISTRY_FIELDS:
        raise ValueError("adapter registry must contain only version and adapters")
    if data.get("version") != "2.0" or not isinstance(data.get("adapters"), list):
        raise ValueError("adapter registry must use version 2.0")
    records: List[Dict[str, str]] = []
    seen_ids = set()
    seen_paths = set()
    for item in data["adapters"]:
        if not isinstance(item, dict) or set(item) != ADAPTER_FIELDS:
            raise ValueError("adapter records must use the small v2 field set")
        record = {}
        for field in ADAPTER_FIELDS:
            value = item[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("adapter.{} must be non-empty text".format(field))
            record[field] = value.strip()
        if ID_PATTERN.fullmatch(record["id"]) is None:
            raise ValueError("adapter id is invalid")
        record["path"] = _safe_path(record["path"], "adapter path")
        record["template"] = _safe_path(record["template"], "adapter template")
        if record["support"] not in {"native", "manual"}:
            raise ValueError("adapter support must be native or manual")
        if record["id"] in seen_ids or record["path"] in seen_paths:
            raise ValueError("adapter ids and output paths must be unique")
        seen_ids.add(record["id"])
        seen_paths.add(record["path"])
        records.append(record)
    return {"version": "2.0", "adapters": records}


def load_adapter_registry(path: Path) -> Dict[str, object]:
    """Load one UTF-8 JSON registry."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("adapter registry must be readable UTF-8 JSON") from error
    return validate_adapter_registry_data(data)


def render_adapter_template(template_path: Path, adapter: Mapping[str, object]) -> str:
    """Read a routing-only adapter template without injecting metadata."""
    if template_path.is_symlink() or not template_path.is_file():
        raise ValueError("adapter template must be a regular file")
    content = template_path.read_text(encoding="utf-8").strip() + "\n"
    if ".ai/rules/index.md" not in content:
        raise ValueError("adapter template must route to .ai/rules/index.md")
    if "adapter-id" in content or "adapter-consumers" in content:
        raise ValueError("adapter template must not embed registry metadata")
    return content


def render_selected_adapters(
    template_root: Path,
    registry: Dict[str, object],
    selected_ids: Iterable[str],
) -> Tuple[List[RenderedAdapter], List[Dict[str, str]], List[str]]:
    """Render each selected tool to its one unique registry path."""
    validated = validate_adapter_registry_data(registry)
    by_id = {record["id"]: record for record in validated["adapters"]}
    selected: List[Dict[str, str]] = []
    unknown: List[str] = []
    seen = set()
    for adapter_id in selected_ids:
        if adapter_id in seen:
            continue
        seen.add(adapter_id)
        record = by_id.get(adapter_id)
        if record is None:
            unknown.append(adapter_id)
        else:
            selected.append(record)
    root = template_root.resolve()
    rendered = []
    for record in selected:
        template = (root / record["template"]).resolve()
        try:
            template.relative_to(root)
        except ValueError as error:
            raise ValueError("adapter template escapes the template root") from error
        rendered.append(
            RenderedAdapter(
                path=record["path"],
                content=render_adapter_template(template, record),
            )
        )
    return rendered, selected, unknown
