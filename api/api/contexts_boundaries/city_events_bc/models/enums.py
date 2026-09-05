from enum import StrEnum


class ReportCategory(StrEnum):
    WATER = "WATER"
    ROADS = "ROADS"
    WASTE = "WASTE"
    GREENERY = "GREENERY"
    LIGHTING = "LIGHTING"
    PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"
    OTHER = "OTHER"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReportStatus(StrEnum):
    # Citizen just filed it; triage event fired.
    SUBMITTED = "SUBMITTED"
    # AI triage in progress on the worker.
    TRIAGING = "TRIAGING"
    # Triage done — waiting in the specialist's HITL review queue.
    PENDING_REVIEW = "PENDING_REVIEW"
    # Specialist approved (kept as an explicit state for audit; PUBLISHED is the
    # citizen-visible terminal state).
    APPROVED = "APPROVED"
    # Specialist rejected — not acted on.
    REJECTED = "REJECTED"
    # Approved and the response is visible to the citizen.
    PUBLISHED = "PUBLISHED"
    # Triage crashed; a specialist can still review the raw report.
    FAILED = "FAILED"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class EventType(StrEnum):
    """What a `city_events` row represents on the citizen map.

    The top layer of the event model: it drives the map glyph, the badge icon
    and the top-level filter, so it stays a small closed set. Finer distinctions
    live in `subtype` and the per-type `details` JSONB (see the migration).
    """

    ISSUE = "ISSUE"  # awaria / usterka
    ALARM = "ALARM"  # alarm / ostrzeżenie
    VENUE = "VENUE"  # miejsce / wydarzenie
    PROMOTION = "PROMOTION"  # promocja (biznes)
    MISSING_PET = "MISSING_PET"  # zaginione / znalezione zwierzę (kot | pies | …)
    HAZARD = "HAZARD"  # zagrożenie — punktowe niebezpieczeństwo
    OUTAGE = "OUTAGE"  # przerwa w dostawie (prąd / woda / gaz / ciepło / internet)
    ROADWORKS = "ROADWORKS"  # roboty / utrudnienia / zamknięcia
    COMMUNITY = "COMMUNITY"  # akcja społeczna — sprzątanie, wolontariat, zbiórki


class EventStatus(StrEnum):
    ACTIVE = "ACTIVE"  # trwa teraz — pokazywane w „aktywne zdarzenia"
    SCHEDULED = "SCHEDULED"  # zaplanowane na przyszłość
    RESOLVED = "RESOLVED"  # zakończone / usunięte
    EXPIRED = "EXPIRED"  # minęło


class EventSource(StrEnum):
    """Who filed the event."""

    CITY = "CITY"  # miasto / urząd
    CITIZEN = "CITIZEN"  # mieszkaniec
    BUSINESS = "BUSINESS"  # firma
