"""ADK tools for data investigation (read-only)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from dq_platform.config import DBT_DIR
from dq_platform.db import get_connection

READ_ONLY_PATTERN = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|attach|copy|install)\b", re.IGNORECASE)


def validate_read_only_sql(sql: str) -> None:
    """Raise ValueError if SQL is not read-only."""
    if not READ_ONLY_PATTERN.match(sql):
        raise ValueError("Only SELECT/WITH queries are allowed")
    if FORBIDDEN.search(sql):
        raise ValueError("Forbidden SQL keyword detected")


def run_sql(sql: str, limit: int = 100) -> str:
    """Execute a read-only SQL query against DuckDB. Returns JSON rows."""
    validate_read_only_sql(sql)
    if "limit" not in sql.lower():
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    with get_connection(read_only=True) as con:
        df = con.execute(sql).df()
    return df.to_json(orient="records", date_format="iso")


def get_schema(table: str) -> str:
    """Return column names and types for a table."""
    with get_connection(read_only=True) as con:
        df = con.execute(f"describe {table}").df()
    return df.to_json(orient="records")


def get_table_profile(table: str, column: str | None = None, date: str | None = None) -> str:
    """Return row count, null rate, and basic stats for a table."""
    date_filter = f"where cast(order_date as date) = '{date}'" if date else ""
    col = column or "order_id"
    sql = f"""
    select
        count(*) as row_count,
        avg(case when {col} is null then 1.0 else 0.0 end) as null_rate,
        count(distinct {col}) as distinct_count
    from {table}
    {date_filter}
    """
    with get_connection(read_only=True) as con:
        df = con.execute(sql).df()
    return df.to_json(orient="records")


def get_metric_history(metric: str, table: str, window: int = 14) -> str:
    """Return daily metric history for a table."""
    if metric == "row_count":
        sql = f"""
        select cast(order_date as date) as metric_date, count(*) as metric_value
        from {table}
        group by 1 order by 1 desc limit {window}
        """
    elif metric == "revenue":
        sql = f"""
        select order_date as metric_date, total_revenue as metric_value
        from main_marts.fct_daily_sales
        order by 1 desc limit {window}
        """
    else:
        sql = f"select count(*) as metric_value from {table}"
    with get_connection(read_only=True) as con:
        df = con.execute(sql).df()
    return df.to_json(orient="records")


def get_freshness(table: str, ts_column: str = "order_timestamp") -> str:
    """Return max timestamp for freshness check."""
    sql = f"select max({ts_column}) as last_seen from {table}"
    with get_connection(read_only=True) as con:
        df = con.execute(sql).df()
    return df.to_json(orient="records")


def get_dbt_lineage(model: str, direction: str = "upstream", depth: int = 3) -> str:
    """Return dbt lineage from manifest.json."""
    manifest_path = DBT_DIR / "target" / "manifest.json"
    if not manifest_path.exists():
        return json.dumps({"error": "manifest.json not found — run dbt compile first"})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = manifest.get("nodes", {})
    model_key = f"model.dq_retail.{model}"
    if model_key not in nodes:
        return json.dumps({"error": f"Model {model} not found"})

    result: list[dict] = []
    visited = set()

    def walk(node_id: str, level: int) -> None:
        if level > depth or node_id in visited:
            return
        visited.add(node_id)
        node = nodes.get(node_id, {})
        result.append({"id": node_id, "name": node.get("name"), "level": level})
        if direction == "upstream":
            for parent in node.get("depends_on", {}).get("nodes", []):
                walk(parent, level + 1)

    walk(model_key, 0)
    return json.dumps(result)


def get_dbt_model(model: str) -> str:
    """Return SQL source and file path for a dbt model."""
    sql_path = DBT_DIR / "models"
    for path in sql_path.rglob(f"{model}.sql"):
        return json.dumps({"path": str(path), "sql": path.read_text(encoding="utf-8")})
    return json.dumps({"error": f"Model file {model}.sql not found"})


def get_dbt_tests(model: str) -> str:
    """List dbt tests related to a model from manifest."""
    manifest_path = DBT_DIR / "target" / "manifest.json"
    if not manifest_path.exists():
        return json.dumps([])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tests = []
    for node_id, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") == "test":
            deps = node.get("depends_on", {}).get("nodes", [])
            if f"model.dq_retail.{model}" in deps:
                tests.append({"test_id": node_id, "name": node.get("name")})
    return json.dumps(tests)


def get_anomaly_history(table: str, metric: str, n: int = 5) -> str:
    """Return recent anomalies for a table/metric."""
    sql = f"""
    select * from dq_anomalies
    where table_name = '{table}' or metric = '{metric}'
    order by detected_at desc limit {n}
    """
    with get_connection(read_only=True) as con:
        try:
            df = con.execute(sql).df()
        except Exception:
            return json.dumps([])
    return df.to_json(orient="records", date_format="iso")


def propose_patch(file_path: str, original_snippet: str, fixed_snippet: str, summary: str) -> str:
    """Propose a code patch (diff summary only — application requires human approval)."""
    allowed = (DBT_DIR / "models").resolve()
    path = Path(file_path).resolve()
    if not str(path).startswith(str(allowed)):
        return json.dumps({"error": "File not in allowlist (dbt/models only)"})
    diff = {
        "file": str(path.relative_to(DBT_DIR.parent)),
        "summary": summary,
        "original": original_snippet,
        "fixed": fixed_snippet,
        "status": "proposed",
    }
    return json.dumps(diff)
