from pypika.terms import Parameter  # type: ignore[import-untyped]


def DBQueryParam(name: str) -> Parameter:
    return Parameter(f"%({name})s")


def DBListQueryParam(name: str) -> Parameter:
    return Parameter(f" ANY (%({name})s)")
