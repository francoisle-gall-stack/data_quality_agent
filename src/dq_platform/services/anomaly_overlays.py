"""Translate persisted DQ anomalies into chart annotations."""

from __future__ import annotations

from typing import Any

from dq_platform.db import get_connection
from dq_platform.services.chart_registry import CHART_ANOMALY_MAP, CHART_REGISTRY


def get_overlays(chart_id: str | None = None) -> list[dict[str, Any]]:
    chart_ids = [chart_id] if chart_id else list(CHART_REGISTRY)
    result: list[dict[str, Any]] = []
    with get_connection(read_only=True) as con:
        try:
            rows = con.execute("select * from dq_anomalies where status = 'open'").fetchdf().to_dict("records")
        except Exception:
            rows = []
    for current_chart in chart_ids:
        allowed = CHART_ANOMALY_MAP.get(current_chart, {}).get("anomaly_types", set())
        for row in rows:
            if row.get("anomaly_type") not in allowed:
                continue
            anomaly_date = row.get("anomaly_date")
            result.append({
                "chart_id": current_chart,
                "anomaly_id": row.get("anomaly_id"),
                "type": row.get("anomaly_type"),
                "severity": row.get("severity"),
                "date_start": anomaly_date,
                "date_end": anomaly_date,
                "label": f"{row.get('anomaly_type')} anomaly",
                "description": f"Observed {row.get('observed_value')} vs expected {row.get('expected_value')}",
            })
    return result
