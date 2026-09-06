"""geo_resolver v1 — exposes the concrete tool as `AGENT` for the resolver."""

from api.ai.geo_resolver.versions.v1.agent import GeoResolver

#: The concrete class the loader picks up when current.yaml selects this version.
AGENT = GeoResolver

__all__ = ["GeoResolver", "AGENT"]
