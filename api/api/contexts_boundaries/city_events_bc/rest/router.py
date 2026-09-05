"""REST routers for citizen reports + the specialist HITL console.

Citizen (`/reports`):
  POST   /reports                     file a report (fires the triage event)
  GET    /reports                      the citizen's own reports
  GET    /reports/{id}                 fetch one of the citizen's reports

Specialist (`/specialist/reports`, guarded by X-Specialist-Key):
  GET    /specialist/reports?status=   the review queue (default PENDING_REVIEW)
  GET    /specialist/reports/{id}      fetch any report for review
  POST   /specialist/reports/{id}/review   APPROVE / REJECT — the HITL decision
"""

import inngest
from api.bootstrap import Bootstrap
from api.contexts_boundaries.auth_bc import (
    CitizenContext,
    SpecialistContext,
    citizen,
    get_bootstrap_dep,
    specialist,
)
from api.contexts_boundaries.city_events_bc.models import IssueReport, ReportStatus
from api.contexts_boundaries.city_events_bc.rest.schemas import (
    ReportListResponse,
    ReportSubmitRequest,
    ReviewRequest,
)
from api.inngest_app import EVENT_REPORT_TRIAGE, inngest_client
from api.shared.exceptions import AccessDeniedError, ConflictError, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, status

reports_router = APIRouter(prefix="/reports", tags=["reports"])
specialist_router = APIRouter(prefix="/specialist/reports", tags=["specialist"])


#
# CITIZEN
#
@reports_router.post("", response_model=IssueReport, status_code=status.HTTP_202_ACCEPTED)
async def submit_report(
    body: ReportSubmitRequest,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> IssueReport:
    report = bootstrap.reports_service.submit_report(
        citizen_id=ctx.citizen_id,
        title=body.title,
        description=body.description,
        category=body.category,
        location_text=body.location_text,
        lat=body.lat,
        lng=body.lng,
    )
    # Hand off to the worker for AI triage; it lands in the specialist queue.
    await inngest_client.send(inngest.Event(name=EVENT_REPORT_TRIAGE, data={"report_id": report.id}))
    return report


@reports_router.get("", response_model=ReportListResponse)
def list_reports(
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> ReportListResponse:
    return ReportListResponse(reports=bootstrap.reports_service.list_reports(ctx.citizen_id))


@reports_router.get("/{report_id}", response_model=IssueReport)
def get_report(
    report_id: int,
    ctx: CitizenContext = Depends(citizen),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> IssueReport:
    try:
        return bootstrap.reports_service.get_owned_or_raise(report_id, ctx.citizen_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zgłoszenie nie istnieje") from exc
    except AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="brak dostępu") from exc


#
# SPECIALIST (HITL)
#
@specialist_router.get("", response_model=ReportListResponse)
def review_queue(
    status: ReportStatus = ReportStatus.PENDING_REVIEW,
    _spec: SpecialistContext = Depends(specialist),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> ReportListResponse:
    return ReportListResponse(reports=bootstrap.reports_service.list_review_queue(status))


@specialist_router.get("/{report_id}", response_model=IssueReport)
def get_report_for_review(
    report_id: int,
    _spec: SpecialistContext = Depends(specialist),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> IssueReport:
    try:
        return bootstrap.reports_service.get_report(report_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zgłoszenie nie istnieje") from exc


@specialist_router.post("/{report_id}/review", response_model=IssueReport)
def review_report(
    report_id: int,
    body: ReviewRequest,
    spec: SpecialistContext = Depends(specialist),
    bootstrap: Bootstrap = Depends(get_bootstrap_dep),
) -> IssueReport:
    try:
        return bootstrap.reports_service.review(
            report_id=report_id,
            specialist_id=spec.specialist_id,
            decision=body.decision,
            edited_category=body.edited_category,
            edited_severity=body.edited_severity,
            edited_department=body.edited_department,
            public_response=body.public_response,
            comment=body.comment,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="zgłoszenie nie istnieje") from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
