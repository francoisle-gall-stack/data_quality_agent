"""DuckDB connection helpers."""

from collections.abc import Iterator
from contextlib import contextmanager

import duckdb

from dq_platform.config import settings


@contextmanager
def get_connection(read_only: bool = True) -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect(str(settings.duckdb_path), read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def query_df(sql: str, read_only: bool = True):
    with get_connection(read_only=read_only) as con:
        return con.execute(sql).df()
