"""Metadata describing dashboard charts and their dbt sources."""

CHART_REGISTRY = {
    "daily_revenue": {"title": "Daily revenue", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "order_revenue"},
    "daily_orders": {"title": "Daily orders", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "order_id"},
    "revenue_by_country": {"title": "Revenue by country", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "order_revenue"},
    "revenue_by_channel": {"title": "Revenue by channel", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "order_revenue"},
    "top_products": {"title": "Top products", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "line_amount"},
    "top_stores": {"title": "Top stores", "primary_table": "main_marts.fct_orders", "dbt_model": "fct_orders", "metric": "order_revenue"},
}

CHART_ANOMALY_MAP = {
    "daily_revenue": {"anomaly_types": {"volume_drop", "freshness_gap", "kpi_drop"}},
    "daily_orders": {"anomaly_types": {"volume_drop", "freshness_gap"}},
    "revenue_by_country": {"anomaly_types": {"dimension_missing"}},
    "revenue_by_channel": {"anomaly_types": {"distribution_shift"}},
    "top_products": {"anomaly_types": {"outliers", "referential_integrity"}},
    "top_stores": {"anomaly_types": set()},
}
