"""Fixtures — thin DI plumbing over the `Bootstrap` container.

Mirrors imprv-api's conftest: almost every fixture just hands out an
already-wired object off the process-wide container (`get_bootstrap()`), so the
TestClient routes and the test itself share one connection pool and one
database.

Scopes:
* session — `config`, `bootstrap`, `db_client`, the factories, and the
  schema-bootstrap (`_db_schema`).
* function — the per-BC services/repositories (cheap; the container caches the
  real singletons behind these accessors).

`_db_schema` creates + migrates the throwaway test DB once, and turns any
connection failure into a `pytest.skip` — so `pytest api/tests/integration` is a
clean no-op when no local Postgres is running.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from api.config import Config


def pytest_collection_modifyitems(config, items) -> None:
    """Auto-mark everything under `api/tests/integration/` with `integration`,
    so `pytest -m "not integration"` runs the fast, infra-free unit suite."""
    for item in items:
        if "/integration/" in str(item.fspath).replace("\\", "/"):
            item.add_marker("integration")


# --------------------------------------------------------------------------- #
# Core container
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def config() -> "Config":
    from api.config import Config

    return Config()


@pytest.fixture(scope="session")
def bootstrap(config: "Config"):
    """The process-wide DI container — the SAME instance the FastAPI routes
    resolve via `get_bootstrap_dep`, so factory writes are visible to requests."""
    from api.bootstrap import get_bootstrap

    return get_bootstrap()


@pytest.fixture(scope="session")
def _db_schema(config: "Config") -> None:
    """Create + migrate the test database; skip the integration layer if the
    server is unreachable."""
    from tests._helpers.db import ensure_test_database

    try:
        ensure_test_database(config)
    except Exception as exc:  # pragma: no cover - infra dependent
        pytest.skip(f"Postgres test database unavailable: {exc}")


@pytest.fixture(scope="session")
def db_client(bootstrap, _db_schema):
    return bootstrap.db_client


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def db_factory(db_client):
    from tests.factories import DBFactory

    return DBFactory(db_client)


@pytest.fixture(scope="session")
def db_agg_factory(db_factory, db_client):
    from tests.factories import DBAggregatesFactory

    return DBAggregatesFactory(db_factory, db_client)


@pytest.fixture(scope="session")
def domain_factory():
    from tests.factories import DomainFactory

    return DomainFactory()


# --------------------------------------------------------------------------- #
# Services & repositories — one-liners off the container (function-scoped, as in
# imprv, so a test can freely `self.mocker.patch.object(...)` on them).
# --------------------------------------------------------------------------- #
@pytest.fixture
def events_service(bootstrap):
    return bootstrap.events_service


@pytest.fixture
def events_repository(bootstrap):
    return bootstrap.events_repository


@pytest.fixture
def reports_service(bootstrap):
    return bootstrap.reports_service


@pytest.fixture
def reports_repository(bootstrap):
    return bootstrap.reports_repository


@pytest.fixture
def conversations_service(bootstrap):
    return bootstrap.conversations_service


@pytest.fixture
def conversations_repository(bootstrap):
    return bootstrap.conversations_repository


@pytest.fixture
def auth_service(bootstrap):
    return bootstrap.auth_service


@pytest.fixture
def citizens_repository(bootstrap):
    return bootstrap.citizens_repository
