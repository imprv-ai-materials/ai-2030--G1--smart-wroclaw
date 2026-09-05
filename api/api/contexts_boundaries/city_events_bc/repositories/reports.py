import abc
from datetime import datetime
from typing import Any

from api.adapters.db import DBClient
from api.contexts_boundaries.city_events_bc.models import (
    IssueReport,
    ReportCategory,
    ReportReview,
    ReportStatus,
    ReviewDecision,
    Severity,
)
from api.contexts_boundaries.city_events_bc.repositories.tables import (
    issue_reports_table,
    report_reviews_table,
)


class AbstractReportsRepository(abc.ABC):
    @abc.abstractmethod
    def create_report(
        self,
        citizen_id: int,
        title: str,
        description: str,
        category: ReportCategory | None = None,
        location_text: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> IssueReport: ...

    @abc.abstractmethod
    def get_report(self, report_id: int) -> IssueReport | None: ...

    @abc.abstractmethod
    def list_reports(self, citizen_id: int) -> list[IssueReport]: ...

    @abc.abstractmethod
    def list_by_status(self, status: ReportStatus) -> list[IssueReport]: ...

    @abc.abstractmethod
    def update_report(self, report_id: int, values: dict[str, Any]) -> IssueReport | None: ...

    @abc.abstractmethod
    def record_review(
        self,
        report_id: int,
        specialist_id: str,
        decision: ReviewDecision,
        report_values: dict[str, Any],
        edited_category: ReportCategory | None = None,
        edited_severity: Severity | None = None,
        edited_department: str | None = None,
        public_response: str | None = None,
        comment: str = "",
    ) -> tuple[IssueReport, ReportReview]: ...


class ReportsRepository(AbstractReportsRepository):
    def __init__(self, db_client: DBClient) -> None:
        self._db = db_client

    def create_report(
        self,
        citizen_id: int,
        title: str,
        description: str,
        category: ReportCategory | None = None,
        location_text: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> IssueReport:
        row = self._db.create_one(
            issue_reports_table,
            values={
                "citizen_id": citizen_id,
                "title": title,
                "description": description,
                "category": category.value if category else None,
                "location_text": location_text,
                "lat": lat,
                "lng": lng,
                "status": ReportStatus.SUBMITTED.value,
            },
        )
        return IssueReport.from_dict(row)

    def get_report(self, report_id: int) -> IssueReport | None:
        row = self._db.get_one(issue_reports_table, {"id": report_id})
        return IssueReport.from_dict(row) if row else None

    def list_reports(self, citizen_id: int) -> list[IssueReport]:
        rows = self._db.get_many(issue_reports_table, criteria={"citizen_id": citizen_id}, order_by="-created_at")
        return [IssueReport.from_dict(r) for r in rows]

    def list_by_status(self, status: ReportStatus) -> list[IssueReport]:
        rows = self._db.get_many(issue_reports_table, criteria={"status": status.value}, order_by="-created_at")
        return [IssueReport.from_dict(r) for r in rows]

    def update_report(self, report_id: int, values: dict[str, Any]) -> IssueReport | None:
        if values:
            values = {**values, "updated_at": datetime.utcnow()}
            self._db.update_one(issue_reports_table, {"id": report_id}, values)
        return self.get_report(report_id)

    def record_review(
        self,
        report_id: int,
        specialist_id: str,
        decision: ReviewDecision,
        report_values: dict[str, Any],
        edited_category: ReportCategory | None = None,
        edited_severity: Severity | None = None,
        edited_department: str | None = None,
        public_response: str | None = None,
        comment: str = "",
    ) -> tuple[IssueReport, ReportReview]:
        """Persist the audit review row AND the resulting report state in one
        transaction — the HITL decision and its effect must land together."""
        with self._db.within_transaction() as tx:
            review_row = tx.create_one(
                report_reviews_table,
                values={
                    "report_id": report_id,
                    "specialist_id": specialist_id,
                    "decision": decision.value,
                    "edited_category": edited_category.value if edited_category else None,
                    "edited_severity": edited_severity.value if edited_severity else None,
                    "edited_department": edited_department,
                    "public_response": public_response,
                    "comment": comment,
                },
            )
            tx.update_one(
                issue_reports_table,
                {"id": report_id},
                {**report_values, "updated_at": datetime.utcnow()},
            )
            report_row = tx.get_one(issue_reports_table, {"id": report_id})
        return IssueReport.from_dict(report_row), ReportReview.from_dict(review_row)
