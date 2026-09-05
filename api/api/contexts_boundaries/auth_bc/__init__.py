"""Auth bounded context.

Real resident login: email + password, JWT, email confirmation, password reset.

The request dependencies (`authenticate`, `require_confirmed_user`,
`optional_user`) and `get_bootstrap_dep` are re-exported LAZILY via PEP 562
`__getattr__`. Eager re-exports would import `api.bootstrap` at package-init
time, and because the composition root imports this BC's repositories/services,
that closes an import cycle. Lazy resolution means
`import api.contexts_boundaries.auth_bc.repositories` (what bootstrap does) never
touches bootstrap, while `from api.contexts_boundaries.auth_bc import
authenticate` still works for routers.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.bootstrap import get_bootstrap_dep
    from api.contexts_boundaries.auth_bc.dependencies import (
        authenticate,
        optional_user,
        require_confirmed_user,
    )

__all__ = [
    "authenticate",
    "get_bootstrap_dep",
    "optional_user",
    "require_confirmed_user",
]

_DEP_NAMES = {
    "authenticate",
    "optional_user",
    "require_confirmed_user",
}


def __getattr__(name: str):
    if name == "get_bootstrap_dep":
        from api.bootstrap import get_bootstrap_dep

        return get_bootstrap_dep
    if name in _DEP_NAMES:
        from api.contexts_boundaries.auth_bc import dependencies

        return getattr(dependencies, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
