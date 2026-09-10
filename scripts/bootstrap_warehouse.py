#!/usr/bin/env python3
"""Create DuckDB warehouse with synthetic raw tables for dbt."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("DUCKDB_PATH", ROOT / "data" / "warehouse.duckdb"))


def _make_customers(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    ids = np.arange(1, n + 1)
    segments = rng.choice(["retail", "wholesale", "vip"], size=n)
    return pd.DataFrame(
        {
            "customer_id": ids,
            "first_name": [f"first_{i}" for i in ids],
            "last_name": [f"last_{i}" for i in ids],
            "email": [f"user{i}@example.com" for i in ids],
            "country_code": rng.choice(["FR", "DE", "US", "UK"], size=n),
            "signup_date": [date(2024, 1, 1) + timedelta(days=int(d)) for d in rng.integers(0, 400, n)],
            "customer_type": segments,
        }
    )


def _make_products(n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(43)
    ids = np.arange(1, n + 1)
    return pd.DataFrame(
        {
            "product_id": ids,
            "product_name": [f"product_{i}" for i in ids],
            "category": rng.choice(["electronics", "clothing", "food"], size=n),
            "unit_price": rng.uniform(5, 200, size=n).round(2),
        }
    )


def _make_stores(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "store_id": np.arange(1, n + 1),
            "store_name": [f"store_{i}" for i in range(1, n + 1)],
            "city": ["Paris", "Lyon", "Berlin", "London", "NYC"] * 2,
            "country_code": ["FR", "FR", "DE", "UK", "US"] * 2,
            "channel": ["store", "web", "store", "web", "store", "web", "store", "web", "store", "web"],
        }
    )


def _make_orders(n: int = 1000, customers: int = 200, stores: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(44)
    ids = np.arange(1, n + 1)
    order_dates = [date(2025, 1, 1) + timedelta(days=int(d)) for d in rng.integers(0, 300, n)]
    statuses = rng.choice(
        ["completed", "confirmed", "shipped", "pending", "cancelled"],
        size=n,
        p=[0.5, 0.15, 0.1, 0.15, 0.1],
    )
    channels = rng.choice(["web", "store", "mobile"], size=n).tolist()
    # Seed data for failure scenarios
    channels[0] = "marketplace"  # SC007 accepted_values failure
    order_dates[1] = date(2026, 8, 9)
    ids[2] = ids[1]  # SC005 duplicate order_id on same date
    order_dates[2] = date(2026, 8, 9)
    order_dates[4] = date(2026, 8, 19)  # SC006 relationships window
    order_dates[5] = date(2026, 8, 19)
    customer_ids = rng.integers(1, customers + 1, size=n).tolist()
    customer_ids[3] = None  # SC004 not_null failure
    return pd.DataFrame(
        {
            "order_id": ids,
            "customer_id": customer_ids,
            "store_id": rng.integers(1, stores + 1, size=n),
            "order_timestamp": [datetime.combine(d, datetime.min.time()) for d in order_dates],
            "order_date": order_dates,
            "status": statuses,
            "channel": channels,
            "country_code": rng.choice(["FR", "DE", "US", "UK"], size=n),
        }
    )


def _make_order_items(orders: pd.DataFrame, products: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(45)
    rows = []
    item_id = 1
    product_prices = {i: round(float(rng.uniform(5, 200)), 2) for i in range(1, products + 1)}
    for _, row in orders.iterrows():
        oid = row["order_id"]
        for _ in range(rng.integers(1, 4)):
            qty = int(rng.integers(1, 5))
            pid = int(rng.integers(1, products + 1))
            price = product_prices[pid]
            rows.append(
                {
                    "order_item_id": item_id,
                    "order_id": oid,
                    "product_id": pid,
                    "quantity": qty,
                    "unit_price": price,
                    "line_amount": round(qty * price, 2),
                }
            )
            item_id += 1
    df = pd.DataFrame(rows)
    # SC006: orphan product for orders in date window
    window_orders = orders[
        (orders["order_date"] >= date(2026, 8, 18)) & (orders["order_date"] <= date(2026, 8, 20))
    ]["order_id"].head(1)
    if len(window_orders):
        df.loc[df.index[0], "order_id"] = window_orders.iloc[0]
        df.loc[df.index[0], "product_id"] = 9999
    return df


def _make_payments(orders: pd.DataFrame) -> pd.DataFrame:
    completed = orders[orders["status"].isin(["completed", "confirmed", "shipped"])]
    rng = np.random.default_rng(46)
    return pd.DataFrame(
        {
            "payment_id": np.arange(1, len(completed) + 1),
            "order_id": completed["order_id"].values,
            "payment_method": rng.choice(["card", "paypal", "cash"], size=len(completed)),
            "payment_status": rng.choice(["paid", "pending", "failed"], size=len(completed), p=[0.9, 0.08, 0.02]),
            "paid_at": [datetime(2025, 6, 1) + timedelta(hours=int(h)) for h in rng.integers(0, 5000, len(completed))],
        }
    )


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    customers = _make_customers()
    products = _make_products()
    stores = _make_stores()
    orders = _make_orders()
    order_items = _make_order_items(orders)
    payments = _make_payments(orders)

    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS main")
    con.register("_customers", customers)
    con.execute("CREATE TABLE main.raw_customers AS SELECT * FROM _customers")
    con.register("_products", products)
    con.execute("CREATE TABLE main.raw_products AS SELECT * FROM _products")
    con.register("_stores", stores)
    con.execute("CREATE TABLE main.raw_stores AS SELECT * FROM _stores")
    con.register("_orders", orders)
    con.execute("CREATE TABLE main.raw_orders AS SELECT * FROM _orders")
    con.register("_order_items", order_items)
    con.execute("CREATE TABLE main.raw_order_items AS SELECT * FROM _order_items")
    con.register("_payments", payments)
    con.execute("CREATE TABLE main.raw_payments AS SELECT * FROM _payments")
    con.close()
    print(f"Created warehouse at {DB_PATH}")


if __name__ == "__main__":
    main()
