"""Render adapter metadata around an identity-neutral routing template."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

from scripts.adapter_registry import (
    resolve_adapter_selection,
    safe_target_path,
    validate_adapter_registry_data,
)


TEMPLATE_METADATA_PATTERN = re.compile(r"<!--\s*TEMPLATE METADATA.*?-->\s*", re.DOTALL)
STATIC_ADAPTER_METADATA_PATTERN = re.compile(
    r"<!--\s*adapter-(?:id|support|scope|loading|consumers)\s*:[^>]+-->\s*",
    re.IGNORECASE,
)
REQUIRED_ADAPTER_FIELDS = ("id", "support", "scope_loading", "import_capability")


@dataclass(frozen=True)
class RenderedAdapter:
    path: str
    content: str


def render_adapter_template(template_path: Path, adapter: Mapping[str, object]) -> str:
    """Prepend selected registry metadata to one static adapter routing body.

    Shared bodies contain no adapter identity. The caller selects a validated registry
    entry, and this renderer supplies the exact identity and loading metadata.
    """
    values = {}
    for field in REQUIRED_ADAPTER_FIELDS:
        value = adapter.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Adapter requires a non-empty {}".format(field))
        values[field] = value.strip()
    consumers = adapter.get("consumers", [values["id"]])
    if not isinstance(consumers, list) or not consumers or not all(
        isinstance(consumer, str) and consumer.strip() for consumer in consumers
    ):
        raise ValueError("Adapter requires non-empty consumers")
    consumer_ids = sorted(set(consumer.strip() for consumer in consumers))
    if values["id"] not in consumer_ids:
        raise ValueError("Adapter consumers must include the adapter owner")
    body = template_path.read_text(encoding="utf-8")
    body = TEMPLATE_METADATA_PATTERN.sub("", body).lstrip()
    body = STATIC_ADAPTER_METADATA_PATTERN.sub("", body).lstrip()
    metadata = "\n".join(
        (
            "<!-- adapter-id: {} -->".format(values["id"]),
            "<!-- adapter-support: {} -->".format(values["support"]),
            "<!-- adapter-scope: {} -->".format(values["scope_loading"]),
            "<!-- adapter-loading: {} -->".format(values["import_capability"]),
            "<!-- adapter-consumers: {} -->".format(",".join(consumer_ids)),
        )
    )
    return "{}\n{}".format(metadata, body)


def concrete_output_path(registry_path: str) -> str:
    """Resolve one deterministic concrete file for a registry path pattern."""
    concrete = registry_path.replace("<rule>", "project")
    parts = concrete.split("/")
    parts[-1] = parts[-1].replace("*", "project-rules")
    return "/".join(parts)


def render_selected_adapters(
    template_root: Path,
    registry: Dict[str, object],
    selected_ids: Iterable[str],
) -> Tuple[List[RenderedAdapter], List[Dict[str, object]], List[str]]:
    """Render one output owner per selected registry output."""
    validate_adapter_registry_data(registry, template_root.resolve(strict=False))
    manifest_adapters, unverified = resolve_adapter_selection(registry, selected_ids)
    rendered: List[RenderedAdapter] = []
    for adapter in manifest_adapters:
        template = safe_target_path(template_root, str(adapter["template"]))
        output_path = concrete_output_path(str(adapter["path"]))
        rendered.append(
            RenderedAdapter(
                path=output_path,
                content=render_adapter_template(template, adapter),
            )
        )
    return (
        sorted(rendered, key=lambda item: item.path),
        manifest_adapters,
        unverified,
    )
