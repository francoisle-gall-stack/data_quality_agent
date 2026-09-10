"""DuckDB schema for DQ store tables."""

DQ_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dq_check_results (
    check_id VARCHAR PRIMARY KEY,
    check_name VARCHAR NOT NULL,
    check_type VARCHAR NOT NULL,
    table_name VARCHAR,
    column_name VARCHAR,
    metric_date DATE,
    observed_value DOUBLE,
    expected_value DOUBLE,
    threshold_value DOUBLE,
    status VARCHAR NOT NULL,
    details VARCHAR,
    executed_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS dq_anomalies (
    anomaly_id VARCHAR PRIMARY KEY,
    check_id VARCHAR,
    anomaly_type VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    column_name VARCHAR,
    metric VARCHAR,
    observed_value DOUBLE,
    expected_value DOUBLE,
    deviation_pct DOUBLE,
    anomaly_date DATE,
    severity VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'open',
    detected_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS dq_metric_history (
    metric_id VARCHAR PRIMARY KEY,
    metric_name VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    metric_date DATE NOT NULL,
    metric_value DOUBLE NOT NULL,
    recorded_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS dq_investigations (
    investigation_id VARCHAR PRIMARY KEY,
    anomaly_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    root_cause VARCHAR,
    confidence DOUBLE,
    business_impact_json VARCHAR,
    recommended_fix_json VARCHAR,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dq_investigation_steps (
    step_id VARCHAR PRIMARY KEY,
    investigation_id VARCHAR NOT NULL,
    step_number INTEGER NOT NULL,
    hypothesis VARCHAR,
    tool_name VARCHAR,
    tool_input_json VARCHAR,
    tool_output_json VARCHAR,
    finding VARCHAR,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS dq_correction_proposals (
    proposal_id VARCHAR PRIMARY KEY,
    investigation_id VARCHAR NOT NULL,
    anomaly_id VARCHAR NOT NULL,
    patch_summary VARCHAR,
    patch_diff VARCHAR,
    affected_files VARCHAR,
    confidence DOUBLE,
    status VARCHAR DEFAULT 'proposed',
    github_pr_url VARCHAR,
    created_at TIMESTAMP DEFAULT current_timestamp
);
"""
