"""HERE Geocoding & Search client — address string → coordinates.

Thin wrapper over HERE's `/discover` endpoint, hard-restricted to a Wrocław
bounding box (`in=bbox:...`) so a query like "ul. Kiełczowska 30" can't resolve
to a same-named street in a neighbouring town. Mirrors the OpenAIClient shape:
unconfigured callers (no `api_key`) branch on `is_configured` and skip
enrichment, so the whole stack stays runnable in local dev without a HERE
account — coordinates just aren't filled until a key is set.

Uses the stdlib HTTP client (no extra dependency). The single blocking call runs
off the event loop in the Inngest worker (`anyio.to_thread`).
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

_DISCOVER_URL = "https://discover.search.hereapi.com/v1/discover"


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float
    label: str
    score: float | None = None
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None
    district: str | None = None


class HereGeocodingClient:
    def __init__(
        self,
        api_key: str | None,
        bbox: str = "16.82,51.02,17.16,51.20",
        lang: str = "pl",
        timeout_s: float = 8.0,
    ) -> None:
        self._api_key = api_key
        self._bbox = bbox
        self._lang = lang
        self._timeout_s = timeout_s

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def geocode(self, query: str) -> GeocodeResult | None:
        """Best in-Wrocław match for a free-form address/place, or None."""
        if not self._api_key:
            raise RuntimeError("HereGeocodingClient not configured (missing api key)")
        q = (query or "").strip()
        if not q:
            return None

        params = urllib.parse.urlencode(
            {
                "q": q,
                "in": f"bbox:{self._bbox}",
                "limit": 1,
                "lang": self._lang,
                "apiKey": self._api_key,
            }
        )
        request = urllib.request.Request(
            f"{_DISCOVER_URL}?{params}", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
            payload = json.load(response)

        for item in payload.get("items") or []:
            position = item.get("position") or {}
            lat, lng = position.get("lat"), position.get("lng")
            if lat is None or lng is None:
                continue
            address = item.get("address") or {}
            return GeocodeResult(
                lat=float(lat),
                lng=float(lng),
                label=item.get("title") or address.get("label") or q,
                score=(item.get("scoring") or {}).get("queryScore"),
                street=address.get("street"),
                house_number=address.get("houseNumber"),
                postal_code=address.get("postalCode"),
                district=address.get("district"),
            )

        logger.info("HERE geocode: no in-Wrocław match for {!r}", q)
        return None
