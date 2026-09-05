"""Shared test utilities (not collected as tests — leading underscore).

Mirrors imprv-api's `tests/_helpers/`: small, dependency-light helpers reused
across the suite. Currently:

* `db.ensure_test_database` — create + migrate the throwaway test DB.
* `jwt.auth_headers` — mint a user bearer token for authenticated requests.
"""
