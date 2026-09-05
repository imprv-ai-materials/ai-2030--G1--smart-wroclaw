from api.contexts_boundaries.city_events_bc.models import (
    IssueReport,
    ReportCategory,
    ReviewDecision,
    Severity,
)
from pydantic import BaseModel, Field


class ReportSubmitRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    category: ReportCategory | None = None
    location_text: str | None = None
    lat: float | None = None
    lng: float | None = None


class ReportListResponse(BaseModel):
    reports: list[IssueReport]


class ReviewRequest(BaseModel):
    decision: ReviewDecision
    # All optional overrides — omitted fields fall back to the AI proposal.
    edited_category: ReportCategory | None = None
    edited_severity: Severity | None = None
    edited_department: str | None = None
    public_response: str | None = None
    comment: str = ""
