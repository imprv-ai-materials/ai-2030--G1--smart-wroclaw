"""Test-suite root — the base test classes every test inherits from.

Ported from the imprv-api conventions (see `tests/README.md`):

* Tests are **class-based** on top of `unittest.IsolatedAsyncioTestCase`, so a
  single class can hold sync *and* `async def test_*` methods with no per-test
  decorator.
* Every class subclasses `BaseUnitTestCase` or `BaseIntegrationTestCase`. Each
  base has one **autouse `init_fixtures` fixture** that pulls the fixtures it
  needs off the DI container (see `conftest.py`) and assigns them onto `self`.
  This is the seam that lets a test just write `self.db_agg_factory`,
  `self.events_service`, `self.client`, `self.mocker`, … .
* Integration DB isolation = `self.db_factory.clear()` (DELETE FROM every table)
  at the start of each test — not transaction rollback. It therefore MUST run
  against a throwaway database, never the dev DB (see the env priming below).

The `api.*` imports at module scope read `api.config` (which requires
`CONFIG__POSTGRES__*`), so we pin the environment BEFORE importing anything from
`api`.
"""

import os

# --------------------------------------------------------------------------- #
# Environment priming — runs at import, before any `api.*` import.
# --------------------------------------------------------------------------- #
# Mount the REST routers + the /ws route deterministically (see api/main.py).
os.environ["SMART_WROCLAW_ROLE"] = "api"
# Point the whole suite at an isolated database. Integration tests DELETE every
# table between cases; running that against the dev DB would wipe local data.
# Override by exporting CONFIG__POSTGRES__DB before invoking pytest.
os.environ.setdefault("CONFIG__POSTGRES__DB", "smart_wroclaw_test")

import unittest  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

import pytest  # noqa: E402

if TYPE_CHECKING:
    from api.config import Config
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture
    from tests.factories import DBAggregatesFactory, DBFactory, DomainFactory


class BaseTestCase(unittest.IsolatedAsyncioTestCase):
    """Root of the hierarchy — shared time + assertion helpers.

    Not collected by pytest (name doesn't match `Test*` and it has no
    `test_*` methods). Subclasses pick up their fixtures via `init_fixtures`.
    """

    maxDiff = None

    def setUp(self) -> None:
        super().setUp()
        # A single "now" pinned per test — handy for building deterministic
        # domain objects without re-reading the clock in each assertion.
        self.now = datetime.now(tz=timezone.utc)

    # -- assertion helpers ------------------------------------------------- #
    def assert_dict_subset(self, subset: dict, whole: dict) -> None:
        """Assert every key/value in `subset` is present and equal in `whole`.

        Ignores extra keys in `whole` — the ergonomic "did the API echo back
        the fields I sent?" check.
        """
        actual = {key: whole.get(key) for key in subset}
        assert actual == subset, f"{actual} != {subset}"


class BaseUnitTestCase(BaseTestCase):
    """Pure-logic tests: no DB, no network. Mock collaborators via `self.mocker`.

    Fixtures injected: `config`, `mocker`, `domain_factory` (in-memory model
    builder). Keep these cheap so unit tests never depend on infra.
    """

    if TYPE_CHECKING:
        config: "Config"
        mocker: "MockerFixture"
        domain_factory: "DomainFactory"

    @pytest.fixture(autouse=True)
    def init_fixtures(
        self,
        config: "Config",
        mocker: "MockerFixture",
        domain_factory: "DomainFactory",
    ) -> None:
        self.config = config
        self.mocker = mocker
        self.domain_factory = domain_factory


class BaseIntegrationTestCase(BaseTestCase):
    """Tests that hit a real Postgres via the DI container + FastAPI TestClient.

    Set up data with `self.db_agg_factory` / `self.db_factory`, call services
    off `self.<service>`, or drive the HTTP surface with `self.client`. Every
    test starts from a clean database (`db_factory.clear()`), and the whole
    layer is skipped when Postgres is unreachable (see `conftest._db_schema`).
    """

    if TYPE_CHECKING:
        config: "Config"
        mocker: "MockerFixture"
        db_factory: "DBFactory"
        db_agg_factory: "DBAggregatesFactory"
        domain_factory: "DomainFactory"
        client: "TestClient"

    @pytest.fixture(autouse=True)
    def init_fixtures(
        self,
        config: "Config",
        mocker: "MockerFixture",
        bootstrap,
        db_client,
        db_factory: "DBFactory",
        db_agg_factory: "DBAggregatesFactory",
        domain_factory: "DomainFactory",
        # services + repositories, pulled off the container (see conftest.py)
        events_service,
        events_repository,
        reports_service,
        reports_repository,
        conversations_service,
        conversations_repository,
        auth_service,
        citizens_repository,
    ) -> None:
        self.config = config
        self.mocker = mocker
        self.bootstrap = bootstrap
        self.db_client = db_client
        self.db_factory = db_factory
        self.db_agg_factory = db_agg_factory
        self.domain_factory = domain_factory

        self.events_service = events_service
        self.events_repository = events_repository
        self.reports_service = reports_service
        self.reports_repository = reports_repository
        self.conversations_service = conversations_service
        self.conversations_repository = conversations_repository
        self.auth_service = auth_service
        self.citizens_repository = citizens_repository

        # Fresh state per test, then a client bound to the (already-imported) app.
        self.db_factory.clear()

        from api.main import app
        from fastapi.testclient import TestClient

        self.client = TestClient(app)
