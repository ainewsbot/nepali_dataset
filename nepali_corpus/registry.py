"""Load and query sources/registry.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "sources" / "registry.yaml"


def load_registry(path: Path | None = None) -> dict[str, dict]:
    with open(path or REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sources = data["sources"]
    for s in sources.values():
        # YAML 1.1 reads bare yes/no as booleans; keep the tri-state string
        r = s.get("redistributable")
        if isinstance(r, bool):
            s["redistributable"] = "yes" if r else "no"
    return sources


def get_source(name: str) -> dict:
    sources = load_registry()
    if name not in sources:
        raise KeyError(f"unknown source {name!r}; known: {', '.join(sorted(sources))}")
    return {"name": name, **sources[name]}
