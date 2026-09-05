"""Auth bounded context.

Real resident login (email + password, JWT, email confirmation, password
reset) lives here, alongside the first-draft header identities kept for the
not-yet-migrated assistant / specialist surfaces.

The request dependencies (`authenticate`, `citizen`, `specialist`, …) and
`get_bootstrap_dep` are re-exported LAZILY via PEP 562 `__getattr__`. Eager
re-exports would import `api.bootstrap` at package-init time, and because the
composition root imports this BC's repositories/services, that closes an import
cycle. Lazy resolution means `import api.contexts_boundaries.auth_bc.repositories`
(what bootstrap does) never touches bootstrap, while
`from api.contexts_boundaries.auth_bc import citizen` still works for routers.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.bootstrap import get_bootstrap_dep
    from api.contexts_boundaries.auth_bc.dependencies import (
        CitizenContext,
        SpecialistContext,
        authenticate,
        citizen,
        require_confirmed_citizen,
        specialist,
    )

__all__ = [
    "CitizenContext",
    "SpecialistContext",
    "authenticate",
    "citizen",
    "get_bootstrap_dep",
    "require_confirmed_citizen",
    "specialist",
]

_DEP_NAMES = {
    "CitizenContext",
    "SpecialistContext",
    "authenticate",
    "citizen",
    "require_confirmed_citizen",
    "specialist",
}


def __getattr__(name: str):
    if name == "get_bootstrap_dep":
        from api.bootstrap import get_bootstrap_dep

        return get_bootstrap_dep
    if name in _DEP_NAMES:
        from api.contexts_boundaries.auth_bc import dependencies

        return getattr(dependencies, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
