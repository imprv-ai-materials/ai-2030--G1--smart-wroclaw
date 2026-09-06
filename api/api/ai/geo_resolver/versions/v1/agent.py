"""geo_resolver · v1 — district lookup + "near me" detection, HERE for addresses.

Three cheap, diacritic-folded passes before any network call:
  1. "moja okolica" / "blisko mnie" → a radius scope flagged `needs_user_location`;
  2. a known Wrocław district name in the text → a district scope;
  3. otherwise, if HERE is configured, geocode the text to a point + radius.
Offline with no district match it returns None — honest about not knowing, rather
than guessing coordinates. The district list is diff-friendly on purpose.
"""

from __future__ import annotations

import re

from api.adapters.geocoding import HereGeocodingClient
from api.ai.geo_resolver.base import AbstractGeoResolver, GeoScope

_DEFAULT_RADIUS_M = 1500

# Wrocław's five districts + the osiedla residents actually name. Extend freely.
_DISTRICTS = (
    "Stare Miasto",
    "Śródmieście",
    "Krzyki",
    "Fabryczna",
    "Psie Pole",
    "Nadodrze",
    "Ołbin",
    "Gądów",
    "Grabiszyn",
    "Sępolno",
    "Biskupin",
    "Maślice",
    "Gaj",
    "Oporów",
    "Brochów",
    "Leśnica",
    "Karłowice",
    "Kleczków",
)
# Folded "near me" tells (matched against the folded input).
_NEIGHBOURHOOD_TELLS = (
    "moja okolic",
    "mojej okolic",
    "w mojej okolic",
    "w poblizu",
    "blisko mnie",
    "kolo mnie",
    "obok mnie",
    "niedaleko mnie",
    "w mojej dzielnic",
)

_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")


def _fold(s: str) -> str:
    return s.lower().translate(_FOLD)


def _common_prefix(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _matches_district(district_fold: str, folded_input: str, folded_tokens: list[str]) -> bool:
    """Polish declines district names ("Krzyki" → "na Krzykach"), so a full-name
    substring misses inflected forms. Match a shared stem instead: for a one-word
    district, any input token that shares a long enough prefix; for a multi-word
    name, fall back to the phrase as written (nominative)."""
    if " " in district_fold:
        return district_fold in folded_input
    threshold = min(6, max(3, len(district_fold) - 1))
    return any(_common_prefix(token, district_fold) >= threshold for token in folded_tokens)


class GeoResolver(AbstractGeoResolver):
    def __init__(
        self,
        geocoding_client: HereGeocodingClient | None = None,
        default_radius_m: int = _DEFAULT_RADIUS_M,
    ) -> None:
        self._geocoder = geocoding_client
        self._default_radius_m = default_radius_m

    def resolve(self, location_text: str) -> GeoScope | None:
        q = (location_text or "").strip()
        if not q:
            return None
        low = _fold(q)

        if any(tell in low for tell in _NEIGHBOURHOOD_TELLS):
            return GeoScope(query=q, radius_m=self._default_radius_m, needs_user_location=True)

        tokens = [_fold(t) for t in re.findall(r"[a-ząćęłńóśźż]+", q.lower())]
        for district in _DISTRICTS:
            if _matches_district(_fold(district), low, tokens):
                return GeoScope(query=q, district=district)

        if self._geocoder is not None and self._geocoder.is_configured:
            result = self._geocoder.geocode(q)
            if result is not None:
                return GeoScope(
                    query=q,
                    lat=result.lat,
                    lng=result.lng,
                    district=result.district,
                    radius_m=self._default_radius_m,
                )
        return None
