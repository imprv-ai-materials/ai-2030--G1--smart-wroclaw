"""Cross-cutting domain exceptions.

Bounded contexts define their own specific errors; these are the shared bases so
the REST layer can map broad families to HTTP codes in one place.
"""


class DomainError(Exception):
    """Base for all domain-level errors."""


class NotFoundError(DomainError):
    """A requested aggregate does not exist."""


class AccessDeniedError(DomainError):
    """The caller is not allowed to act on this aggregate."""


class ConflictError(DomainError):
    """The action conflicts with the aggregate's current state."""
