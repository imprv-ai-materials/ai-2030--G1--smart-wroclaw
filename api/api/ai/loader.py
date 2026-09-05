"""Resolve the CURRENT version of an agent from its `versions/current.yaml`.

`current.yaml` names a version (e.g. `v1`); the loader imports
`api.ai.<agent>.versions.<version>` and hands back its `AGENT` class plus an
optional per-deployment model override. `bootstrap.agents` then constructs it.

This is the one indirection that turns "which version runs" into a one-line YAML
edit instead of a code change — the numbered `versions/vN/` packages are all
present, so promotion (or rollback) never needs a rebuild.
"""

import importlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

AI_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class CurrentVersion:
    """The resolved active version of an agent."""

    agent_name: str
    version: str
    model: str | None
    agent_class: type


@lru_cache(maxsize=None)
def load_current(agent_name: str) -> CurrentVersion:
    """Read `ai/<agent_name>/versions/current.yaml` and resolve its `AGENT` class."""
    path = AI_DIR / agent_name / "versions" / "current.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"No CURRENT pointer for agent '{agent_name}' (expected {path}). "
            "Add a versions/current.yaml naming the active version."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        version = str(data["version"])
    except KeyError as exc:  # a pointer with no version is a mistake, not a default
        raise ValueError(f"{path} is missing required key 'version'") from exc

    module = importlib.import_module(f"api.ai.{agent_name}.versions.{version}")
    try:
        agent_class = module.AGENT
    except AttributeError as exc:
        raise ValueError(
            f"{module.__name__} does not export `AGENT` — each versions/<v>/__init__.py "
            "must expose the concrete agent class as AGENT."
        ) from exc

    return CurrentVersion(agent_name=agent_name, version=version, model=data.get("model"), agent_class=agent_class)
