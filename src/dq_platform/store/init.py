"""Initialize DQ store tables in DuckDB."""

from dq_platform.db import get_connection
from dq_platform.store.schema import DQ_SCHEMA_SQL


def init_dq_store() -> None:
    with get_connection(read_only=False) as con:
        for stmt in DQ_SCHEMA_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                con.execute(s)
