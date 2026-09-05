"""Citizen issue reports + the specialist HITL review loop.

The lifecycle:

    submit()      SUBMITTED   → fire triage event
    run_triage()  TRIAGING    → PENDING_REVIEW   (AI proposal attached)  [worker]
    review()      PENDING_REVIEW → PUBLISHED / REJECTED                  [specialist]

`run_triage` is deliberately the ONLY automated status change; publication ALWAYS
requires a human `review()`. That human-in-the-loop gate is the whole point — the
AI triages, a specialist decides. The specialist may override every field the AI
proposed before the response goes out to the citizen.
"""

from datetime import datetime

from api.ai.triage_agent import AbstractTriageAgent
from api.contexts_boundaries.city_events_bc.models import (
    IssueReport,
    ReportCategory,
    ReportStatus,
    ReviewDecision,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories import AbstractReportsRepository
from api.shared.exceptions import AccessDeniedError, ConflictError, NotFoundError
from loguru import logger


class ReportsService:
    def __init__(self, repository: AbstractReportsRepository, triage_agent: AbstractTriageAgent) -> None:
        self._repo = repository
        self._triage_agent = triage_agent

    #
    # CITIZEN SIDE
    #
    def submit_report(
        self,
        citizen_id: int,
        title: str,
        description: str,
        category: ReportCategory | None = None,
        location_text: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> IssueReport:
        return self._repo.create_report(
            citizen_id=citizen_id,
            title=title.strip(),
            description=description.strip(),
            category=category,
            location_text=location_text,
            lat=lat,
            lng=lng,
        )

    def list_reports(self, citizen_id: int) -> list[IssueReport]:
        return self._repo.list_reports(citizen_id)

    def get_owned_or_raise(self, report_id: int, citizen_id: int) -> IssueReport:
        report = self._repo.get_report(report_id)
        if report is None:
            raise NotFoundError(f"report {report_id} not found")
        if report.citizen_id != citizen_id:
            raise AccessDeniedError(f"report {report_id} not owned by citizen {citizen_id}")
        return report

    def get_report(self, report_id: int) -> IssueReport:
        report = self._repo.get_report(report_id)
        if report is None:
            raise NotFoundError(f"report {report_id} not found")
        return report

    #
    # WORKER — AI triage
    #
    def run_triage(self, report_id: int) -> None:
        report = self._repo.get_report(report_id)
        if report is None:
            logger.warning("run_triage: report {} vanished", report_id)
            return
        if report.status not in (ReportStatus.SUBMITTED, ReportStatus.FAILED):
            logger.info("run_triage: report {} not awaiting triage (status={})", report_id, report.status)
            return

        self._repo.update_report(report_id, {"status": ReportStatus.TRIAGING.value})
        try:
            triage = self._triage_agent.triage(report)
            self._repo.update_report(
                report_id,
                {
                    "status": ReportStatus.PENDING_REVIEW.value,
                    "triage": triage.model_dump(mode="json"),
                    # Seed the effective fields from the proposal; the specialist
                    # can still override them on approval.
                    "severity": triage.severity.value,
                    "department": triage.department,
                    "category": (report.category or triage.category).value,
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("triage failed for report {}", report_id)
            self._repo.update_report(report_id, {"status": ReportStatus.FAILED.value})
            raise

    #
    # SPECIALIST SIDE — the human-in-the-loop review
    #
    def list_review_queue(self, status: ReportStatus = ReportStatus.PENDING_REVIEW) -> list[IssueReport]:
        return self._repo.list_by_status(status)

    def review(
        self,
        report_id: int,
        specialist_id: str,
        decision: ReviewDecision,
        edited_category: ReportCategory | None = None,
        edited_severity: Severity | None = None,
        edited_department: str | None = None,
        public_response: str | None = None,
        comment: str = "",
    ) -> IssueReport:
        report = self._repo.get_report(report_id)
        if report is None:
            raise NotFoundError(f"report {report_id} not found")
        if report.status not in (ReportStatus.PENDING_REVIEW, ReportStatus.FAILED):
            raise ConflictError(f"report {report_id} is not awaiting review (status={report.status.value})")

        if decision == ReviewDecision.APPROVE:
            # The specialist's edits win; fall back to the AI proposal, then the
            # citizen's original category.
            category = edited_category or report.category or (report.triage.category if report.triage else None)
            severity = edited_severity or report.severity or (report.triage.severity if report.triage else None)
            department = edited_department or report.department or (report.triage.department if report.triage else None)
            response = public_response or (report.triage.suggested_response if report.triage else "")
            report_values = {
                "status": ReportStatus.PUBLISHED.value,
                "category": category.value if category else None,
                "severity": severity.value if severity else None,
                "department": department,
                "public_response": response,
                "reviewed_by": specialist_id,
                "reviewed_at": datetime.utcnow(),
            }
        else:
            report_values = {
                "status": ReportStatus.REJECTED.value,
                "public_response": public_response,
                "reviewed_by": specialist_id,
                "reviewed_at": datetime.utcnow(),
            }

        updated, _review = self._repo.record_review(
            report_id=report_id,
            specialist_id=specialist_id,
            decision=decision,
            report_values=report_values,
            edited_category=edited_category,
            edited_severity=edited_severity,
            edited_department=edited_department,
            public_response=public_response,
            comment=comment,
        )
        return updated
