"""Background AI triage of a citizen report.

The REST layer persists the report and fires `smart_wroclaw/report.triage`. This
function — hosted on the worker — runs the triage agent and moves the report into
the specialist review queue (`PENDING_REVIEW`). It never publishes: a human always
makes the final call (see city_events_bc/services/reports.py::review).
"""

import anyio.to_thread
import inngest
from api.bootstrap import get_bootstrap
from api.inngest_app import EVENT_EVENT_GEOCODE, EVENT_REPORT_TRIAGE, inngest_client


@inngest_client.create_function(
    fn_id="report-triage",
    trigger=inngest.TriggerEvent(event=EVENT_REPORT_TRIAGE),
    singleton=inngest.Singleton(key="event.data.report_id", mode="skip"),
    retries=1,
)
async def report_triage(ctx: inngest.Context) -> dict:
    report_id = int(ctx.event.data["report_id"])
    bootstrap = get_bootstrap()
    await anyio.to_thread.run_sync(bootstrap.reports_service.run_triage, report_id)
    report = bootstrap.reports_service.get_report(report_id)
    return {"report_id": report_id, "status": report.status.value}


REPORTS_INNGEST_FUNCTIONS = [report_triage]


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
