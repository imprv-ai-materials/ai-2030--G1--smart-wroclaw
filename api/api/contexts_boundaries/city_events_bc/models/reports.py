from datetime import datetime
from typing import Any

from api.contexts_boundaries.city_events_bc.models.enums import (
    ReportCategory,
    ReportStatus,
    ReviewDecision,
    Severity,
)
from pydantic import BaseModel


class TriageResult(BaseModel):
    """The AI's structured assessment of a citizen report.

    This is a *proposal* — nothing here reaches the citizen until a human
    specialist approves it in the HITL review step. The specialist can override
    every field before publishing.
    """

    category: ReportCategory = ReportCategory.OTHER
    severity: Severity = Severity.MEDIUM
    department: str = ""
    summary: str = ""
    suggested_response: str = ""
    is_duplicate: bool = False
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TriageResult | None":
        if not data:
            return None
        return cls.model_validate(data)


class IssueReport(BaseModel):
    id: int
    citizen_id: int
    title: str
    description: str
    category: ReportCategory | None = None
    location_text: str | None = None
    lat: float | None = None
    lng: float | None = None
    status: ReportStatus
    # Effective (approved) triage fields — seeded by the AI, possibly overridden
    # by the specialist on approval.
    severity: Severity | None = None
    department: str | None = None
    triage: TriageResult | None = None
    # Set on approval; this is what the citizen sees.
    public_response: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueReport":
        return cls(
            id=data["id"],
            citizen_id=data["citizen_id"],
            title=data["title"],
            description=data["description"],
            category=ReportCategory(data["category"]) if data.get("category") else None,
            location_text=data.get("location_text"),
            lat=data.get("lat"),
            lng=data.get("lng"),
            status=ReportStatus(data["status"]),
            severity=Severity(data["severity"]) if data.get("severity") else None,
            department=data.get("department"),
            triage=TriageResult.from_dict(data.get("triage")),
            public_response=data.get("public_response"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=data.get("reviewed_at"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class ReportReview(BaseModel):
    """An audit record of one HITL decision by a specialist."""

    id: int
    report_id: int
    specialist_id: str
    decision: ReviewDecision
    edited_category: ReportCategory | None = None
    edited_severity: Severity | None = None
    edited_department: str | None = None
    public_response: str | None = None
    comment: str = ""
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportReview":
        return cls(
            id=data["id"],
            report_id=data["report_id"],
            specialist_id=data["specialist_id"],
            decision=ReviewDecision(data["decision"]),
            edited_category=ReportCategory(data["edited_category"]) if data.get("edited_category") else None,
            edited_severity=Severity(data["edited_severity"]) if data.get("edited_severity") else None,
            edited_department=data.get("edited_department"),
            public_response=data.get("public_response"),
            comment=data.get("comment") or "",
            created_at=data["created_at"],
        )
