"""event_extractor v1 — exposes the concrete agent as `AGENT` for the resolver."""

from api.ai.event_extractor.versions.v1.agent import EventExtractor

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = EventExtractor

__all__ = ["EventExtractor", "AGENT"]
