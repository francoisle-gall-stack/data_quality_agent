"""Parameterized warehouse queries used by the React dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any

from dq_platform.db import get_connection


def _filters(start: date, end: date, countries: list[str], channels: list[str], alias: str = "") -> tuple[str, list[Any]]:
    prefix = f"{alias}." if alias else ""
    clauses = [f"{prefix}order_date between ? and ?"]
    params: list[Any] = [start, end]
    if countries:
        clauses.append(f"{prefix}country_code in ({','.join('?' for _ in countries)})")
        params.extend(countries)
    if channels:
        clauses.append(f"{prefix}channel in ({','.join('?' for _ in channels)})")
        params.extend(channels)
    return " and ".join(clauses), params


def query_df(sql: str, params: list[Any] | None = None):
    with get_connection(read_only=True) as con:
        return con.execute(sql, params or []).df()


def get_filters() -> dict[str, Any]:
    dates = query_df("select min(order_date) as min_date, max(order_date) as max_date from main_marts.fct_orders")
    refresh = query_df("select max(order_date) as data_refresh_date from main_marts.fct_daily_sales")
    countries = query_df("select distinct country_code from main_marts.fct_orders order by 1")
    channels = query_df("select distinct channel from main_marts.fct_orders order by 1")
    return {
        "min_date": dates.iloc[0]["min_date"],
        "max_date": dates.iloc[0]["max_date"],
        "data_refresh_date": refresh.iloc[0]["data_refresh_date"],
        "countries": countries["country_code"].tolist(),
        "channels": channels["channel"].tolist(),
    }


def get_kpis(start: date, end: date, countries: list[str], channels: list[str]) -> list[dict[str, Any]]:
    where, params = _filters(start, end, countries, channels)
    return query_df(
        f"""select count(distinct order_id) as orders,
        count(distinct customer_id) as active_customers,
        coalesce(sum(order_revenue), 0) as revenue,
        coalesce(avg(order_revenue), 0) as avg_basket
        from main_marts.fct_orders where {where}""",
        params,
    ).to_dict(orient="records")


def get_daily_trends(start: date, end: date, countries: list[str], channels: list[str]) -> list[dict[str, Any]]:
    where, params = _filters(start, end, countries, channels)
    return query_df(
        f"""select order_date, count(distinct order_id) as orders, sum(order_revenue) as revenue
        from main_marts.fct_orders where {where} group by 1 order by 1""",
        params,
    ).to_dict(orient="records")


def get_breakdown(dimension: str, start: date, end: date, countries: list[str], channels: list[str]) -> list[dict[str, Any]]:
    if dimension not in {"country_code", "channel"}:
        raise ValueError("Unsupported breakdown")
    where, params = _filters(start, end, countries, channels)
    return query_df(
        f"""select {dimension}, sum(order_revenue) as revenue, count(*) as orders
        from main_marts.fct_orders where {where} group by 1 order by revenue desc""",
        params,
    ).to_dict(orient="records")


def get_top_products(start: date, end: date, countries: list[str], channels: list[str]) -> list[dict[str, Any]]:
    where, params = _filters(start, end, countries, channels, "o")
    return query_df(
        f"""select p.product_name, p.category, sum(oi.line_amount) as revenue, sum(oi.quantity) as units
        from main_marts.fct_orders o
        join main_staging.stg_order_items oi on o.order_id = oi.order_id
        join main_marts.dim_products p on oi.product_id = p.product_id
        where {where} group by 1, 2 order by revenue desc limit 15""",
        params,
    ).to_dict(orient="records")


def get_top_stores(start: date, end: date, countries: list[str], channels: list[str]) -> list[dict[str, Any]]:
    where, params = _filters(start, end, countries, channels, "o")
    return query_df(
        f"""select s.store_name, s.country_code, sum(o.order_revenue) as revenue, count(*) as orders
        from main_marts.fct_orders o join main_marts.dim_stores s on o.store_id = s.store_id
        where {where} group by 1, 2 order by revenue desc limit 10""",
        params,
    ).to_dict(orient="records")
