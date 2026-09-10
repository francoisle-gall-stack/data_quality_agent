"""Streamlit business dashboard — explore retail KPIs."""

import plotly.express as px
import streamlit as st

from dq_platform.db import query_df

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Retail Analytics", layout="wide")
st.title("Retail Analytics Dashboard")
st.caption("E-commerce demo dataset — August 2026")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")

    # Date range — bounded by min/max order dates in the dataset
    date_range = query_df(
        "select min(order_date) as min_d, max(order_date) as max_d from main_marts.fct_orders"
    )
    min_d = date_range["min_d"].iloc[0]
    max_d = date_range["max_d"].iloc[0]

    start = st.date_input("Start date", value=min_d, min_value=min_d, max_value=max_d)
    end = st.date_input("End date", value=max_d, min_value=min_d, max_value=max_d)

    # Country — all distinct values pre-selected by default
    countries = query_df("select distinct country_code from main_marts.fct_orders order by 1")
    country_opts = countries["country_code"].tolist()
    selected_countries = st.multiselect("Country", country_opts, default=country_opts)

    # Channel — web, mobile, store, marketplace
    channels = query_df("select distinct channel from main_marts.fct_orders order by 1")
    channel_opts = channels["channel"].tolist()
    selected_channels = st.multiselect("Channel", channel_opts, default=channel_opts)

# ---------------------------------------------------------------------------
# SQL filter clauses — built from sidebar selections
# ---------------------------------------------------------------------------
country_filter = ", ".join(f"'{c}'" for c in selected_countries) or "''"
channel_filter = ", ".join(f"'{c}'" for c in selected_channels) or "''"

# Single-table queries on fct_orders (no alias needed)
base_where = f"""
    order_date between '{start}' and '{end}'
    and country_code in ({country_filter})
    and channel in ({channel_filter})
"""

# Join queries where fct_orders is aliased as "o" — columns must be qualified
# to avoid ambiguity (e.g. country_code exists on both fct_orders and dim_stores)
base_where_o = f"""
    o.order_date between '{start}' and '{end}'
    and o.country_code in ({country_filter})
    and o.channel in ({channel_filter})
"""

# ---------------------------------------------------------------------------
# KPI summary cards
# ---------------------------------------------------------------------------
kpi_sql = f"""
select
    count(distinct order_id) as orders,
    count(distinct customer_id) as active_customers,
    coalesce(sum(order_revenue), 0) as revenue,
    coalesce(avg(order_revenue), 0) as avg_basket
from main_marts.fct_orders
where {base_where}
"""
kpis = query_df(kpi_sql).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue (EUR)", f"{kpis['revenue']:,.0f}")
c2.metric("Orders", f"{int(kpis['orders']):,}")
c3.metric("Active customers", f"{int(kpis['active_customers']):,}")
c4.metric("Avg basket (EUR)", f"{kpis['avg_basket']:,.2f}")

# ---------------------------------------------------------------------------
# Daily trends — revenue and order count over time
# ---------------------------------------------------------------------------
st.subheader("Daily trends")
daily = query_df(f"""
select order_date, count(distinct order_id) as orders, sum(order_revenue) as revenue
from main_marts.fct_orders
where {base_where}
group by 1 order by 1
""")
if not daily.empty:
    fig_rev = px.line(daily, x="order_date", y="revenue", title="Daily revenue")
    fig_ord = px.line(daily, x="order_date", y="orders", title="Daily orders")
    st.plotly_chart(fig_rev, use_container_width=True)
    st.plotly_chart(fig_ord, use_container_width=True)

# ---------------------------------------------------------------------------
# Breakdown by dimension — country and channel side by side
# ---------------------------------------------------------------------------
st.subheader("Breakdown by dimension")
col_a, col_b = st.columns(2)

by_country = query_df(f"""
select country_code, sum(order_revenue) as revenue, count(*) as orders
from main_marts.fct_orders where {base_where}
group by 1 order by revenue desc
""")
if not by_country.empty:
    col_a.plotly_chart(px.bar(by_country, x="country_code", y="revenue", title="Revenue by country"))

by_channel = query_df(f"""
select channel, sum(order_revenue) as revenue, count(*) as orders
from main_marts.fct_orders where {base_where}
group by 1 order by revenue desc
""")
if not by_channel.empty:
    col_b.plotly_chart(px.bar(by_channel, x="channel", y="revenue", title="Revenue by channel"))

# ---------------------------------------------------------------------------
# Top products — revenue and units sold, joined via order items
# ---------------------------------------------------------------------------
st.subheader("Top products")
top_products = query_df(f"""
select p.product_name, p.category, sum(oi.line_amount) as revenue, sum(oi.quantity) as units
from main_marts.fct_orders o
join main_staging.stg_order_items oi on o.order_id = oi.order_id
join main_marts.dim_products p on oi.product_id = p.product_id
where {base_where_o}
group by 1, 2 order by revenue desc limit 15
""")
if not top_products.empty:
    st.dataframe(top_products, use_container_width=True)

# ---------------------------------------------------------------------------
# Top stores — revenue and order count per physical store
# ---------------------------------------------------------------------------
st.subheader("Top stores")
top_stores = query_df(f"""
select s.store_name, s.country_code, sum(o.order_revenue) as revenue, count(*) as orders
from main_marts.fct_orders o
join main_marts.dim_stores s on o.store_id = s.store_id
where {base_where_o}
group by 1, 2 order by revenue desc limit 10
""")
if not top_stores.empty:
    st.dataframe(top_stores, use_container_width=True)

# ---------------------------------------------------------------------------
# Drill-down by date — individual orders for a single day
# ---------------------------------------------------------------------------
st.subheader("Drill-down by date")
drill_date = st.date_input("Select date", value=end, min_value=min_d, max_value=max_d, key="drill")
drill = query_df(f"""
select order_id, customer_id, channel, country_code, order_status, order_revenue
from main_marts.fct_orders
where order_date = '{drill_date}'
  and country_code in ({country_filter})
  and channel in ({channel_filter})
order by order_revenue desc limit 50
""")
st.dataframe(drill, use_container_width=True)
