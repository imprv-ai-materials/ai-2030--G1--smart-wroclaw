# Testing conventions

Ported from the imprv-api test suite. The goal is that a developer moving
between the two repos feels at home.

## Layout — mirror the source package

```
api/tests/
  __init__.py          # base test classes + env priming (imported as `tests`)
  conftest.py          # DI-accessor fixtures over the Bootstrap container
  factories.py         # DBFactory / DomainFactory / DBAggregatesFactory
  _helpers/            # shared utilities (underscore => not collected)
  unit/                # pure logic, no DB, no network      (BaseUnitTestCase)
    adapters/  ai/  contexts_boundaries/<bc>/
  integration/         # real Postgres + TestClient   (BaseIntegrationTestCase)
    contexts_boundaries/<bc>/  entrypoints/
```

Every directory is a package (`__init__.py`) so tests import the base classes
with `from tests import BaseUnitTestCase`.

## Base classes (in `tests/__init__.py`)

Tests are **class-based** on `unittest.IsolatedAsyncioTestCase` — one class can
hold sync and `async def test_*` methods with no per-test decorator. Subclass:

* `BaseUnitTestCase` — injects `self.config`, `self.mocker`, `self.domain_factory`.
* `BaseIntegrationTestCase` — injects the above plus `self.db_factory`,
  `self.db_agg_factory`, the per-BC services/repositories, and a fresh
  `self.client` (FastAPI `TestClient`). It calls `db_factory.clear()` before
  each test.

Each base wires its fixtures onto `self` via a single **autouse `init_fixtures`
fixture** — that's the seam that lets a test just say `self.events_service`.

## Naming

* Methods: `test_<unit>__<scenario>__<expected_outcome>`
  (e.g. `test_post_event__unconfirmed_email__403`).
* Classes: `class Test<Thing>(BaseXTestCase)`.

## GIVEN / WHEN / THEN

Arrange under `# GIVEN`, the single call-under-test under `# WHEN`, assertions
under `# THEN`, a blank line between blocks. Mock via `self.mocker` (pytest-mock),
never the bare `unittest.mock`.

## Building cases with `parameterized`

Because tests are class-based we use the `parameterized` library, **not**
`@pytest.mark.parametrize`. A case is a `param("<description>", ...=..., expected=...)`;
the leading description is the case id, absorbed by the method as `_`:

```python
@parameterized.expand([
    param("status only → both ACTIVE", status=EventStatus.ACTIVE, type_=None, expected=2),
    param("no filter → the whole feed", status=None, type_=None, expected=3),
])
def test_list_events__filters(self, _, status, type_, expected):
    ...
```

## Factories

* `DomainFactory` — in-memory pydantic models (unit tests): `self.domain_factory.issue_report(...)`.
* `DBFactory` — persists a row and returns the dict; one `<entity>_db(...)` per table.
* `DBAggregatesFactory` → `DynamicalAggregator` — the **"agg" factory**: a fluent,
  label-keyed builder that composes `DBFactory` calls and resolves references by
  label. Chain builders, then read rows back with `.get(group, label)`:

```python
agg = (
    self.db_agg_factory.create()
    .create_citizen("resident", email_confirmed=True)
    .create_issue_report("report", citizen_label="resident")
    .create_report_review("review", report_label="report")
)
report = agg.get("issue_reports", "report")
```

All factory kwargs default to a `faker` value, so a test only spells out the
fields it actually asserts on.

## Running

```bash
poetry run pytest api/tests                 # everything
poetry run pytest -m "not integration"      # fast unit-only (no DB)
poetry run pytest api/tests/integration     # DB-backed (auto-skips if no PG)
```

Integration tests point at an **isolated** database (`smart_wroclaw_test` by
default — override via `CONFIG__POSTGRES__DB`). `tests/_helpers/db.py` creates it
and runs `alembic upgrade head`; if Postgres is unreachable the whole
integration layer is skipped, never failed.
```
