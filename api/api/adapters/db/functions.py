from typing import Any

from pypika.functions import (  # type: ignore[import-untyped]
    DistinctOptionFunction,
    Function,
)


class ArrayContains(Function):
    def __init__(self, column: Any, value: Any, alias: str | None = None) -> None:
        super().__init__("ANY", value, column, alias=alias)

    def get_function_sql(self, **kwargs: Any) -> str:
        value_sql = self.args[0].get_sql(**kwargs)
        column_sql = self.args[1].get_sql(**kwargs)
        return f"{value_sql} = ANY({column_sql})"


class ArrayAgg(DistinctOptionFunction):
    def __init__(self, term: str, alias: str | None = None) -> None:
        super().__init__("ARRAY_AGG", term, alias=alias)
