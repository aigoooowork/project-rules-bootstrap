"""Render adapter metadata around an identity-neutral routing template."""

import re
from pathlib import Path
from typing import Mapping


TEMPLATE_METADATA_PATTERN = re.compile(r"<!--\s*TEMPLATE METADATA.*?-->\s*", re.DOTALL)
REQUIRED_ADAPTER_FIELDS = ("id", "support", "scope_loading", "import_capability")


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
    body = template_path.read_text(encoding="utf-8")
    body = TEMPLATE_METADATA_PATTERN.sub("", body).lstrip()
    metadata = "\n".join(
        (
            "<!-- adapter-id: {} -->".format(values["id"]),
            "<!-- adapter-support: {} -->".format(values["support"]),
            "<!-- adapter-scope: {} -->".format(values["scope_loading"]),
            "<!-- adapter-loading: {} -->".format(values["import_capability"]),
        )
    )
    return "{}\n{}".format(metadata, body)
