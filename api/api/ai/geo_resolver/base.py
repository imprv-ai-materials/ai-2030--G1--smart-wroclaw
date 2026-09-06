"""Contract for the `geo_resolver` — the shared location tool.

Turns a location mention in a resident's message into a machine scope the search
and analytics lanes can filter by: a named Wrocław district, or a point + radius.
It's a tool (not an LLM agent), but it lives here as a versioned component with its
own contract + dataset so it's swappable and testable like the rest.

`needs_user_location` flags the "moja okolica" case: the text says "near me" but the
tool alone can't know where "me" is — the caller must supply the user's home point
(from profile or browser geolocation). Surfacing it as a flag keeps that product
decision explicit instead of silently guessing.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class GeoScope(BaseModel):
    query: str
    district: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    # True when the scope is relative to the user ("near me") and the caller must
    # fill lat/lng from the user's stored/te location before it can be applied.
    needs_user_location: bool = False


class AbstractGeoResolver(ABC):
    @abstractmethod
    def resolve(self, location_text: str) -> GeoScope | None:
        """Resolve a location mention to a scope, or None if nothing usable is found."""
        ...
