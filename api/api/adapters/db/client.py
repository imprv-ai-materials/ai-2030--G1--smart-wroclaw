"""Thin pypika-over-psycopg query helper.

A deliberately small active-record-ish surface (`get_one`, `get_many`,
`create_one`, `update_one`, `delete_many`, `within_transaction`) that every
repository composes queries with. Criteria dicts support Django-ish suffixes
(`field__in`, `field__gte`, `field__ilike`, …) resolved in `where()`. Copied
across imprv services — keep it generic; no domain code lives here.
"""

import json
from typing import Any, Callable, Literal, cast

from api.adapters.db.functions import ArrayContains
from api.adapters.db.params import DBListQueryParam, DBQueryParam  # noqa: F401
from loguru import logger
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pypika import Order, Parameter
from pypika import PostgreSQLQuery as Query
from pypika.functions import Count
from pypika.queries import Column, QueryBuilder, Table
from pypika.terms import ValueWrapper


class RawSQL(ValueWrapper):
    """Wrapper for raw SQL expressions that should not be escaped."""

    def get_sql(self, **kwargs):
        return self.value


class DBClient:
    def __init__(
        self,
        connection_pool: ConnectionPool,
        enable_query_logging: bool = False,
        enable_parameter_logging: bool = False,
        statement_timeout_ms: int = 10000,
    ) -> None:
        self._connection_pool = connection_pool
        self._statement_timeout_ms = statement_timeout_ms
        self._enable_query_logging = enable_query_logging
        self._enable_parameter_logging = enable_parameter_logging

    def within_transaction(self) -> "TransactionalDBClient":
        return TransactionalDBClient(
            connection_pool=self._connection_pool,
            enable_query_logging=self._enable_query_logging,
            enable_parameter_logging=self._enable_parameter_logging,
        )

    def _log_query(self, sql: str, parameters: dict[str, Any] | None) -> None:
        if not self._enable_query_logging:
            return
        if self._enable_parameter_logging:
            logger.debug("db query: {} params={}", sql, parameters)
        else:
            logger.debug("db query: {}", sql)

    def _execute_with_connection_pool(
        self,
        sql: str,
        parameters: dict[str, Any] | None,
        result_func: Callable[[Any], Any],
        use_dict_row: bool = False,
    ):
        with self._connection_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row if use_dict_row else None) as cur:
                self.set_configs(cur)
                cur.execute(sql, parameters or {})
                return result_func(cur)

    #
    # CREATE
    #
    def create_many(
        self,
        table: Table,
        values: list[dict],
        returning: Literal["ALL", "ID"] | list[Column] = "ALL",
    ) -> list[dict]:
        if not values:
            return []

        columns = values[0].keys()
        q = Query.into(table).columns(*columns)
        parametrized_values: dict[str, Any] = {}
        for i, v in enumerate(values):
            v, v_params = self.parametrize_values(v, prefix=f"values_{i}")
            parametrized_values = {**parametrized_values, **v_params}
            q = q.insert(*[v[c] for c in columns])

        if returning == "ALL":
            q = q.returning("*")
        elif returning == "ID":
            q = q.returning("id")
        else:
            q = q.returning(*returning)

        return self.query_many(q=q, parameters=parametrized_values)

    def create_one(
        self,
        table: Table,
        values: dict[str, Any],
        returning: Literal["ALL", "ID"] | list[Column] = "ALL",
    ):
        return self.create_many(table=table, values=[values], returning=returning)[0]

    def get_or_create(
        self,
        table: Table,
        criteria: dict[str, Any],
    ) -> tuple[dict | None, bool]:
        created = False
        if not (res := self.get_one(table, criteria)):
            res = self.create_one(table, criteria)
            created = True
        return res, created

    #
    # READ
    #
    def get_many(
        self,
        table: Table,
        criteria: dict[str, Any],
        select: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        group_by: str | None = None,
        distinct: bool = False,
        distinct_on: str | None = None,
    ) -> list[dict]:
        q = Query.from_(table)
        q = q.select(*select) if select else q.select("*")

        criteria, criteria_params = self.parametrize_dict(criteria, prefix="criteria")
        if where := self.where(table, criteria, criteria_params):
            q = q.where(where)

        if limit:
            q = q.limit(DBQueryParam("limit"))
        if offset:
            q = q.offset(DBQueryParam("offset"))

        if distinct_on:
            q = q.distinct_on(distinct_on)

        if distinct_on and order_by:
            order_by = order_by.strip()
            if order_by.startswith("-"):
                q = q.orderby(distinct_on, order=Order.asc)
                q = q.orderby(order_by[1:], order=Order.desc)
            else:
                if order_by == distinct_on:
                    q = q.orderby(order_by, order=Order.asc)
                else:
                    q = q.orderby(distinct_on, order=Order.asc)
                    q = q.orderby(order_by, order=Order.asc)
        elif distinct_on:
            q = q.orderby(distinct_on, order=Order.asc)
        elif order_by and order_by[0] == "-":
            q = q.orderby(order_by[1:], order=Order.desc)
        elif order_by:
            q = q.orderby(order_by, order=Order.asc)

        if group_by:
            q = q.groupby(group_by)
        if distinct:
            q = q.distinct()

        return (
            self.query_many(
                q,
                parameters={
                    "limit": limit,
                    "offset": offset,
                    **criteria_params,
                },
            )
            or []
        )

    def get_one(
        self,
        table: Table,
        criteria: dict[str, Any],
        select: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict | None:
        res = self.get_many(table, criteria, limit=limit, offset=offset, select=select)
        if not res:
            return None
        if len(res) > 1:
            raise ValueError("More than one result found matching the criteria. Expected only one.")
        return res[0]

    def count(self, table: Table, criteria: dict[str, Any]) -> int:
        q = Query.from_(table).select(Count("1")).as_("count")
        criteria, criteria_params = self.parametrize_dict(criteria, prefix="criteria")
        if where := self.where(table, criteria, criteria_params):
            q = q.where(where)
        return cast("dict", self.query_one(q, parameters=criteria_params))["count"]

    #
    # UPDATE
    #
    def update_many(
        self,
        table: Table,
        criteria: list[dict[str, Any]],
        values: list[dict[str, Any]],
    ) -> bool:
        total_affected = 0
        for c, v in zip(criteria, values):
            if self.update_one(table, c, v):
                total_affected += 1
        return total_affected > 0

    def update_one(
        self,
        table: Table,
        criteria: dict[str, Any],
        values: dict[str, Any],
    ) -> bool:
        q = Query.update(table)

        values, values_params = self.parametrize_values(values, prefix="value")
        for k, v in values.items():
            q = q.set(k, v)

        criteria, criteria_params = self.parametrize_dict(criteria, prefix="criteria")
        if where := self.where(table, criteria, criteria_params):
            q = q.where(where)

        rows_affected = self.execute(q, parameters={**values_params, **criteria_params})
        if rows_affected is not None:
            if isinstance(rows_affected, int):
                return rows_affected > 0
            if isinstance(rows_affected, list):
                return len(rows_affected) > 0
        return False

    #
    # DELETE
    #
    def delete_many(self, table: Table, criteria: dict[str, Any]) -> bool:
        q = Query.from_(table)
        criteria, criteria_params = self.parametrize_dict(criteria, prefix="criteria")
        if where := self.where(table, criteria, criteria_params):
            q = q.where(where)
        q = q.delete()
        rows_affected = self.execute(q, parameters=criteria_params)
        if rows_affected is not None:
            if isinstance(rows_affected, int):
                return rows_affected > 0
            if isinstance(rows_affected, list):
                return len(rows_affected) > 0
        return False

    #
    # HELPERS
    #
    def parametrize_values(
        self,
        d: dict[str, Any],
        prefix: str | None = None,
    ) -> tuple[dict[str, Parameter], dict[str, Any]]:
        parameters: dict[str, Parameter] = {}
        parametrized_values: dict[str, Any] = {}
        prefix = prefix or "p"
        for k, v in d.items():
            parameters[k] = DBQueryParam(f"{prefix}_{k}")
            value: Any = v
            # Postgres text/jsonb cannot store NUL (\x00) — LLM output
            # occasionally emits one mid-string. Strip it before writing: from
            # the JSON escape for dict/list, and from raw text columns.
            if isinstance(v, (dict, list)):
                value = json.dumps(v).replace("\\u0000", "")
            elif isinstance(v, str):
                value = v.replace("\x00", "")
            parametrized_values[f"{prefix}_{k}"] = value
        return parameters, parametrized_values

    def parametrize_dict(
        self,
        d: dict[str, Any],
        prefix: str | None = None,
    ) -> tuple[dict[str, Parameter], dict[str, Any]]:
        parameters: dict[str, Parameter | list[Parameter]] = {}
        parametrized_values: dict[str, Any] = {}
        prefix = prefix or "p"
        for k, v in d.items():
            if k.endswith("__in") or k.endswith("__not_in"):
                parameters[k] = []
                for i, e in enumerate(v):
                    parameters[k].append(DBQueryParam(f"{prefix}_{k}_{i}"))
                    parametrized_values[f"{prefix}_{k}_{i}"] = e
            elif v is None:
                parameters[k] = DBQueryParam(f"{prefix}_{k}__isnull")
                parametrized_values[f"{prefix}_{k}__isnull"] = v
            else:
                parameters[k] = DBQueryParam(f"{prefix}_{k}")
                parametrized_values[f"{prefix}_{k}"] = v
        return parameters, parametrized_values

    def where(self, table: Table, criteria: dict[str, Any], parametrized_values: dict[str, Any] | None = None) -> Any:
        where = None
        for k, v in criteria.items():
            if k.endswith("__in"):
                expr = getattr(table, k.replace("__in", "")).isin(v)
            elif k.endswith("__not_in"):
                expr = getattr(table, k.replace("__not_in", "")).notin(v)
            elif k.endswith("__ne"):
                expr = getattr(table, k.replace("__ne", "")) != v
            elif k.endswith("__ilike"):
                expr = getattr(table, k.replace("__ilike", "")).ilike(v)
            elif k.endswith("__gte"):
                expr = getattr(table, k.replace("__gte", "")) >= v
            elif k.endswith("__gt"):
                expr = getattr(table, k.replace("__gt", "")) > v
            elif k.endswith("__lte"):
                expr = getattr(table, k.replace("__lte", "")) <= v
            elif k.endswith("__lt"):
                expr = getattr(table, k.replace("__lt", "")) < v
            elif k.endswith("__not_null"):
                expr = getattr(table, k.replace("__not_null", "")).isnotnull()
            elif k.endswith("__isnull"):
                expr = getattr(table, k.replace("__isnull", "")).isnull()
            elif k.endswith("__contains"):
                expr = ArrayContains(getattr(table, k.replace("__contains", "")), v)
            elif v is None or (isinstance(v, Parameter) and "__isnull" in v.get_sql()):
                expr = getattr(table, k).isnull()
            else:
                expr = getattr(table, k) == v

            where = expr if not where else where & expr
        return where

    def query_one(self, q: QueryBuilder, parameters: dict[str, Any] | None = None) -> dict | None:
        res = self.query_many(q, parameters=parameters)
        return res[0] if res else None

    def query_many(self, q: QueryBuilder, parameters: dict[str, Any] | None = None) -> list[dict]:
        return self.execute_with_output(q, parameters=parameters) or []

    def execute(self, q: QueryBuilder, parameters: dict[str, Any] | None = None) -> int:
        sql = q.get_sql()
        self._log_query(sql, parameters)
        return self._execute_with_connection_pool(sql, parameters, lambda cur: cur.rowcount)

    def execute_with_output(
        self,
        q: QueryBuilder,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict]:
        sql = q.get_sql()
        self._log_query(sql, parameters)
        return self._execute_with_connection_pool(sql, parameters, lambda cur: cur.fetchall(), use_dict_row=True)

    def set_configs(self, cur) -> None:
        if self._statement_timeout_ms:
            cur.execute(f"SET statement_timeout TO '{self._statement_timeout_ms}ms'")


class TransactionalDBClient(DBClient):
    """A DBClient bound to a single connection + open transaction (context
    manager). Use for multi-write invariants — e.g. persisting a report review
    and flipping the report status atomically."""

    def __init__(
        self,
        connection_pool: ConnectionPool,
        enable_query_logging: bool = False,
        enable_parameter_logging: bool = False,
    ) -> None:
        super().__init__(
            connection_pool=connection_pool,
            enable_query_logging=enable_query_logging,
            enable_parameter_logging=enable_parameter_logging,
        )
        self._connection = None
        self._cursor = None
        self._transaction = None

    def __enter__(self) -> "TransactionalDBClient":
        self._connection = self._connection_pool.connection()
        conn = self._connection.__enter__()  # type: ignore[attr-defined]
        self._cursor = conn.cursor(row_factory=dict_row)
        self._cursor.__enter__()  # type: ignore[attr-defined]
        self._transaction = conn.transaction()
        self._transaction.__enter__()  # type: ignore[attr-defined]
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._transaction.__exit__(exc_type, exc_value, traceback)
        self._transaction = None
        self._cursor.__exit__(exc_type, exc_value, traceback)
        self._cursor = None
        self._connection.__exit__(exc_type, exc_value, traceback)
        self._connection = None

    def execute(self, q: QueryBuilder, parameters: dict[str, Any] | None = None) -> int:
        sql = q.get_sql()
        if not self._cursor:
            raise RuntimeError("Trying to execute a query without a cursor.")
        self._log_query(sql, parameters)
        self.set_configs(self._cursor)
        self._cursor.execute(sql, parameters or {})
        return self._cursor.rowcount

    def execute_with_output(
        self,
        q: QueryBuilder,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict]:
        sql = q.get_sql()
        if not self._cursor:
            raise RuntimeError("Trying to execute a query without a cursor.")
        self._log_query(sql, parameters)
        self.set_configs(self._cursor)
        self._cursor.execute(sql, parameters or {})
        return self._cursor.fetchall()
