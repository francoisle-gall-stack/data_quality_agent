"""Deterministic SQL quality check runner."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from dq_platform.config import QUALITY_SQL_DIR
from dq_platform.db import get_connection
from dq_platform.store.init import init_dq_store

CHECK_TYPE_MAP = {
    "check_volume_drop": "volume_drop",
    "check_freshness": "freshness_gap",
    "check_null_rate": "null_rate_spike",
    "check_duplicates": "duplicates",
    "check_distribution_shift": "distribution_shift",
    "check_kpi_drop": "kpi_drop",
    "check_dimension_missing": "dimension_missing",
    "check_outliers": "outliers",
    "check_referential_integrity": "referential_integrity",
    "check_dbt_transformation": "dbt_transformation_error",
}


def _severity(deviation: float | None) -> str:
    if deviation is None:
        return "medium"
    if abs(deviation) >= 50:
        return "critical"
    if abs(deviation) >= 25:
        return "high"
    return "medium"


def run_sql_checks(sql_dir: Path | None = None) -> list[dict]:
    sql_dir = sql_dir or QUALITY_SQL_DIR
    init_dq_store()
    results: list[dict] = []

    with get_connection(read_only=False) as con:
        con.execute("delete from dq_anomalies")
        con.execute("delete from dq_check_results")

    sql_files = sorted(sql_dir.glob("*.sql"))
    for sql_file in sql_files:
        check_name = sql_file.stem
        check_type = CHECK_TYPE_MAP.get(check_name, check_name)
        sql = sql_file.read_text(encoding="utf-8")

        with get_connection(read_only=True) as con:
            df = con.execute(sql).df()

        status = "pass" if df.empty else "fail"
        check_id = str(uuid.uuid4())

        with get_connection(read_only=False) as con:
            if not df.empty:
                for _, row in df.iterrows():
                    row_check_id = str(uuid.uuid4())
                    raw_observed = row.get("observed_value", 0) or 0
                    try:
                        observed = float(raw_observed)
                    except (TypeError, ValueError):
                        observed = 0.0
                    expected = row.get("expected_value")
                    expected_f = float(expected) if expected is not None and pd.notna(expected) else None
                    deviation = None
                    if expected_f and expected_f != 0:
                        deviation = round((observed - expected_f) / abs(expected_f) * 100, 2)

                    metric_date = row.get("metric_date")
                    anomaly_id = f"DET-{uuid.uuid4().hex[:8].upper()}"

                    con.execute(
                        """
                        insert into dq_check_results (
                            check_id, check_name, check_type, table_name, column_name,
                            metric_date, observed_value, expected_value, threshold_value,
                            status, details, executed_at
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            row_check_id,
                            check_name,
                            check_type,
                            "raw_orders" if "raw" in check_name else "fct_daily_sales",
                            None,
                            metric_date,
                            observed,
                            expected_f,
                            None,
                            status,
                            f"Failed on {metric_date}",
                            datetime.utcnow(),
                        ],
                    )
                    con.execute(
                        """
                        insert into dq_anomalies (
                            anomaly_id, check_id, anomaly_type, table_name, column_name,
                            metric, observed_value, expected_value, deviation_pct,
                            anomaly_date, severity, status, detected_at
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            anomaly_id,
                            row_check_id,
                            check_type,
                            "raw_orders" if check_type != "dbt_transformation_error" else "int_order_revenue",
                            None,
                            check_type,
                            observed,
                            expected_f,
                            deviation,
                            metric_date,
                            _severity(deviation),
                            "open",
                            datetime.utcnow(),
                        ],
                    )
                    results.append(
                        {
                            "anomaly_id": anomaly_id,
                            "check_name": check_name,
                            "anomaly_type": check_type,
                            "table": "raw_orders",
                            "metric": check_type,
                            "observed_value": observed,
                            "expected_value": expected_f,
                            "deviation": deviation,
                            "date": str(metric_date),
                        }
                    )
            else:
                con.execute(
                    """
                    insert into dq_check_results (
                        check_id, check_name, check_type, table_name, column_name,
                        metric_date, observed_value, expected_value, threshold_value,
                        status, details, executed_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        check_id,
                        check_name,
                        check_type,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        status,
                        "All checks passed",
                        datetime.utcnow(),
                    ],
                )

    return results


def main() -> None:
    anomalies = run_sql_checks()
    print(f"DQ checks complete. {len(anomalies)} anomalies detected.")
    for a in anomalies:
        print(f"  - {a['anomaly_id']}: {a['anomaly_type']} on {a['date']}")
