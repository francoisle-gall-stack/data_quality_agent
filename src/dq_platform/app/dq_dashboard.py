"""Streamlit Data Quality monitoring dashboard."""


import pandas as pd
import streamlit as st

from dq_platform.db import query_df
from dq_platform.quality.runner import run_sql_checks

st.set_page_config(page_title="Data Quality Monitor", layout="wide", page_icon="🔍")
st.title("Data Quality Monitoring")
st.caption("Deterministic SQL checks + agentic investigation")

if st.button("Run SQL quality checks"):
    with st.spinner("Running checks..."):
        anomalies = run_sql_checks()
    st.success(f"Checks complete — {len(anomalies)} anomalies detected")

try:
    anomalies_df = query_df("select * from dq_anomalies order by detected_at desc")
    checks_df = query_df("select * from dq_check_results order by executed_at desc limit 50")
except Exception:
    anomalies_df = pd.DataFrame()
    checks_df = pd.DataFrame()

if anomalies_df.empty and checks_df.empty:
    st.info("No DQ results yet. Click 'Run SQL quality checks' to start.")
else:
    open_count = len(anomalies_df[anomalies_df["status"] == "open"]) if not anomalies_df.empty else 0
    critical = (
        len(anomalies_df[anomalies_df["severity"] == "critical"]) if not anomalies_df.empty else 0
    )
    tables_impacted = anomalies_df["table_name"].nunique() if not anomalies_df.empty else 0
    score = max(0, 100 - open_count * 8 - critical * 15)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DQ Score", f"{score}/100")
    c2.metric("Open anomalies", open_count)
    c3.metric("Critical", critical)
    c4.metric("Tables impacted", tables_impacted)

    st.subheader("Detected anomalies")
    if not anomalies_df.empty:
        st.dataframe(
            anomalies_df[
                [
                    "anomaly_id",
                    "anomaly_type",
                    "table_name",
                    "metric",
                    "observed_value",
                    "expected_value",
                    "deviation_pct",
                    "anomaly_date",
                    "severity",
                    "status",
                ]
            ],
            use_container_width=True,
        )

        selected = st.selectbox("Incident detail", anomalies_df["anomaly_id"].tolist())
        row = anomalies_df[anomalies_df["anomaly_id"] == selected].iloc[0]
        st.json(
            {
                "anomaly_id": row["anomaly_id"],
                "type": row["anomaly_type"],
                "table": row["table_name"],
                "metric": row["metric"],
                "observed": row["observed_value"],
                "expected": row["expected_value"],
                "deviation_pct": row["deviation_pct"],
                "date": str(row["anomaly_date"]),
                "severity": row["severity"],
            }
        )

    st.subheader("Recent check results")
    if not checks_df.empty:
        st.dataframe(checks_df, use_container_width=True)

st.subheader("Agent investigation")
st.markdown(
    "Run agent investigation from CLI: `dq-investigate` (requires `GOOGLE_API_KEY` and Langfuse keys)."
)
st.markdown("Traces are sent to Langfuse when configured.")
