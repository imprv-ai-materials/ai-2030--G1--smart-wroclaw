"""Offline triage heuristics — the no-OpenAI-key fallback that keeps the HITL
queue usable in local dev. Pure unit tests: no DB, no network.

Demonstrates the imprv conventions: a class on `BaseUnitTestCase`, cases built
with `parameterized.expand` + `param("<name>", ..., expected=...)`, the leading
description absorbed as `_`, GIVEN/WHEN/THEN structure, and domain objects built
via `self.domain_factory`.
"""

from api.adapters.llm import OpenAIClient
from api.ai.triage_agent.versions.v1.agent import TriageAgent
from api.contexts_boundaries.city_events_bc.models import ReportCategory, Severity
from parameterized import param, parameterized
from tests import BaseUnitTestCase

DEFAULT_DEPARTMENT = "Centrum Zarządzania Kryzysowego"


class TestTriageAgentOfflineTriage(BaseUnitTestCase):
    def _agent(self, default_department: str = DEFAULT_DEPARTMENT) -> TriageAgent:
        return TriageAgent(OpenAIClient(api_key=None), default_department=default_department)

    @parameterized.expand(
        [
            param(
                "water leak → WATER / CRITICAL, routed to MPWiK",
                title="Wyciek wody na Traugutta",
                description="Leci woda z hydrantu, zalany chodnik, zagrożenie poślizgiem",
                expected_category=ReportCategory.WATER,
                expected_severity=Severity.CRITICAL,
                expected_department="MPWiK",
            ),
            param(
                "pothole → ROADS, routed to ZDiUM",
                title="Dziura w jezdni",
                description="Ogromny wybój na ulicy, uszkadza auta",
                expected_category=ReportCategory.ROADS,
                expected_severity=None,  # severity not asserted for this case
                expected_department="ZDiUM",
            ),
            param(
                "unclassifiable → OTHER, falls back to the default department",
                title="Coś dziwnego",
                description="Nie wiem jak to opisać",
                expected_category=ReportCategory.OTHER,
                expected_severity=None,
                expected_department=DEFAULT_DEPARTMENT,
            ),
        ]
    )
    def test_triage__by_keywords__classifies_and_routes(
        self, _, title, description, expected_category, expected_severity, expected_department
    ) -> None:
        # GIVEN a report whose text carries domain-specific keywords
        report = self.domain_factory.issue_report(title=title, description=description)

        # WHEN the offline triage agent assesses it
        result = self._agent().triage(report)

        # THEN it lands in the expected category / department
        assert result.category is expected_category
        assert result.department == expected_department
        if expected_severity is not None:
            assert result.severity is expected_severity
        # AND a draft reply + a valid confidence are always produced
        assert result.suggested_response
        assert 0.0 <= result.confidence <= 1.0

    def test_triage__citizen_declared_category__is_respected(self) -> None:
        # GIVEN a report where the citizen already chose a category
        report = self.domain_factory.issue_report(
            title="Latarnia nie świeci",
            description="Przepalona żarówka w lampie",
            category=ReportCategory.LIGHTING,
        )

        # WHEN it is triaged offline
        result = self._agent().triage(report)

        # THEN the agent keeps the citizen's declared category
        assert result.category is ReportCategory.LIGHTING
