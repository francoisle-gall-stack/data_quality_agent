"""Streamlit UI for dbt failure investigation — no agent logic."""

from __future__ import annotations

import asyncio
import uuid

import streamlit as st

from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
from dbt_failure_pipeline.core.state import (
    get_current_incident_id,
    list_incidents,
    load_incident,
    save_incident,
    set_current_incident_id,
)
from dbt_failure_pipeline.deterministic import run_dbt_build, run_diagnostic
from dbt_failure_pipeline.orchestration.fix_pipeline import run_fix_pipeline
from dbt_failure_pipeline.orchestration.pipeline import run_correction, run_investigation
from dbt_failure_pipeline.scenarios.manager import (
    activate_scenario,
    get_active_scenario,
    list_scenarios,
    get_scenario_info,
    reset_scenario,
)


def _run_async(coro):
    return asyncio.run(coro)


st.set_page_config(page_title="dbt Failure Investigator", layout="wide")
st.title("Agentic dbt Failure Investigator")

scenarios = list_scenarios()
col1, col2 = st.columns(2)

with col1:
    scenario_id = st.selectbox("Scenario", scenarios, index=0 if scenarios else None)
    reset_first = st.checkbox("Reset before activate", value=True)
    if scenario_id:
        scenario_info = get_scenario_info(scenario_id)
        st.caption(scenario_info["description"])

with col2:
    active = get_active_scenario()
    st.info(f"Active scenario: {active or 'none'}")

if st.button("1. Activate scenario & run dbt build", type="primary"):
    if reset_first:
        reset_scenario()
    activate_scenario(scenario_id)
    result = run_dbt_build()
    if result.success:
        st.error("dbt build succeeded — scenario did not produce a failure.")
    else:
        diagnostic = run_diagnostic()
        if not diagnostic.has_errors:
            st.error("dbt build failed but no error nodes found in run_results.json.")
        else:
            incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
            record = InvestigationRecord(
                incident_id=incident_id,
                scenario_id=scenario_id,
                status=IncidentStatus.OPEN,
                diagnostic=diagnostic,
            )
            save_incident(record)
            set_current_incident_id(incident_id)
            st.session_state["incident_id"] = incident_id
            st.success(f"Incident created: {incident_id}")
            st.json(diagnostic.model_dump())

incident_id = st.session_state.get("incident_id") or get_current_incident_id()
if incident_id:
    st.subheader(f"Incident {incident_id}")
    record = load_incident(incident_id)

    record = st.session_state.get("record") or record

    with st.expander("Diagnostic", expanded=False):
        st.json(record.diagnostic.model_dump())

    if record.status in (IncidentStatus.OPEN, IncidentStatus.NEEDS_HUMAN) and st.button(
        "2. Run investigation"
    ):
        with st.spinner("Running deterministic context → Investigation..."):
            record = _run_async(run_investigation(incident_id))
        st.session_state["record"] = record

    with st.expander("Investigation / RCA", expanded=True):
        st.write(record.investigation_output or "(not run)")

    if st.button("3. Generate correction"):
        with st.spinner("Running correction agent..."):
            record = _run_async(run_correction(incident_id))
        st.session_state["record"] = record

    with st.expander("Proposed patch", expanded=True):
        if record.patch:
            st.write(record.patch.summary)
            st.code(record.patch.diff_unified or "(empty diff)", language="diff")
        else:
            st.write(record.correction_output or "(no patch yet)")

    if record.status == IncidentStatus.AWAITING_APPROVAL and record.patch and st.button(
        "4. Approve & apply fix", type="primary"
    ):
        with st.spinner("Applying patch, running dbt compile/test..."):
            record = run_fix_pipeline(incident_id, human_approved=True)
        st.session_state["record"] = record
        if record.validation_passed:
            st.success("Validation passed!")
        else:
            st.warning("Validation failed — needs human review.")
        if record.pr_url:
            st.link_button("Open PR", record.pr_url)

    st.caption(f"Status: {record.status.value}")

with st.sidebar:
    st.header("Recent incidents")
    for inc in list_incidents()[:10]:
        st.text(f"{inc.incident_id} — {inc.scenario_id} — {inc.status.value}")
