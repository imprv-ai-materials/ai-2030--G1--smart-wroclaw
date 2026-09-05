"""Background enrichment of a city_events row.

The REST/chat layer persists the event and fires `smart_wroclaw/event.geocode`;
this function — hosted on the worker — resolves the event's location string to
coordinates via HERE and persists them.
"""

import anyio.to_thread
import inngest
from api.bootstrap import get_bootstrap
from api.inngest_app import EVENT_EVENT_GEOCODE, inngest_client


@inngest_client.create_function(
    fn_id="event-geocode",
    trigger=inngest.TriggerEvent(event=EVENT_EVENT_GEOCODE),
    # Latest location wins: a newer change cancels an in-flight geocode.
    singleton=inngest.Singleton(key="event.data.event_id", mode="cancel"),
    retries=2,
)
async def geocode_event(ctx: inngest.Context) -> dict:
    """Resolve an event's location string to coordinates via HERE and persist
    them. Fired after an event's location is added/changed (city_events REST)."""
    event_id = int(ctx.event.data["event_id"])
    bootstrap = get_bootstrap()
    event = await anyio.to_thread.run_sync(
        bootstrap.events_service.geocode_event, event_id
    )
    return {"event_id": event_id, "lat": event.lat, "lng": event.lng}


EVENTS_INNGEST_FUNCTIONS = [geocode_event]
