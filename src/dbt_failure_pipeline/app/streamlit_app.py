"""Streamlit UI for dbt failure investigation — no agent logic."""

from __future__ import annotations

import asyncio
import difflib
import html
import uuid

import streamlit as st

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
from dbt_failure_pipeline.core.state import (
    get_current_incident_id,
    list_incidents,
    load_incident,
    save_incident,
    set_current_incident_id,
)
from dbt_failure_pipeline.deterministic import (
    extract_dbt_error_text,
    prioritize_failed_nodes_for_scenario,
    run_dbt_build,
    run_diagnostic,
)
from dbt_failure_pipeline.evaluation.classification import classify_diagnostic, is_auto_fixable
from dbt_failure_pipeline.orchestration.fix_pipeline import run_fix_pipeline
from dbt_failure_pipeline.orchestration.pipeline import run_correction, run_investigation
from dbt_failure_pipeline.scenarios.manager import (
    activate_scenario,
    get_active_scenario,
    get_scenario_info,
    list_scenarios,
    reset_scenario,
)


def _run_async(coro):
    return asyncio.run(coro)


def _check_duckdb_available() -> str | None:
    """Return a user-facing message when DuckDB cannot be opened for dbt."""
    path = settings.duckdb_path
    if not path.exists():
        return f"DuckDB file not found: {path}"
    try:
        import duckdb

        conn = duckdb.connect(str(path), read_only=False)
        conn.close()
    except Exception as exc:
        message = str(exc)
        if "cannot open file" in message.lower() or "already open" in message.lower():
            return (
                f"DuckDB is locked ({path}). Close other connections "
                "(Cursor tab, API server, another terminal) and retry."
            )
        return f"Cannot open DuckDB: {exc}"
    return None


def _infrastructure_error_message(diagnostic) -> str | None:
    """Explain why investigation was skipped for infrastructure failures."""
    if is_auto_fixable(diagnostic):
        return None
    category = classify_diagnostic(diagnostic)
    if category.value != "infrastructure":
        return (
            f"Investigation skipped: {category.value} error is not auto-fixable. "
            "See Diagnostic for details."
        )
    node = diagnostic.primary_failed_node
    detail = ""
    if node and node.error_message:
        for line in node.error_message.splitlines():
            if "already open in" in line.lower():
                detail = line.strip()
                break
        if not detail and "cannot open file" in node.error_message.lower():
            detail = "DuckDB file is locked by another process."
    return (
        "Investigation skipped: DuckDB is locked and dbt could not run. "
        f"{detail} Close other connections, then run the pipeline again."
    ).strip()


def _render_side_by_side_diff(original: str, corrected: str) -> None:
    original_lines = original.splitlines()
    corrected_lines = corrected.splitlines()
    matcher = difflib.SequenceMatcher(None, original_lines, corrected_lines)
    rows = []

    def cell(line_number: int | None, content: str, change: str = "") -> str:
        number = "" if line_number is None else str(line_number)
        escaped = html.escape(content)
        return (
            f'<td class="line-number">{number}</td>'
            f'<td class="code-line {change}">{escaped or "&nbsp;"}</td>'
        )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset, (left, right) in enumerate(
                zip(original_lines[i1:i2], corrected_lines[j1:j2])
            ):
                rows.append(
                    f"<tr>{cell(i1 + offset + 1, left)}"
                    f"{cell(j1 + offset + 1, right)}</tr>"
                )
        elif tag == "replace":
            count = max(i2 - i1, j2 - j1)
            for offset in range(count):
                left = original_lines[i1 + offset] if i1 + offset < i2 else ""
                right = corrected_lines[j1 + offset] if j1 + offset < j2 else ""
                left_number = i1 + offset + 1 if i1 + offset < i2 else None
                right_number = j1 + offset + 1 if j1 + offset < j2 else None
                rows.append(
                    f"<tr>{cell(left_number, left, 'removed')}"
                    f"{cell(right_number, right, 'added')}</tr>"
                )
        elif tag == "delete":
            for offset, line in enumerate(original_lines[i1:i2]):
                rows.append(
                    f"<tr>{cell(i1 + offset + 1, line, 'removed')}"
                    f"{cell(None, '', 'empty')}</tr>"
                )
        elif tag == "insert":
            for offset, line in enumerate(corrected_lines[j1:j2]):
                rows.append(
                    f"<tr>{cell(None, '', 'empty')}"
                    f"{cell(j1 + offset + 1, line, 'added')}</tr>"
                )

    st.markdown(
        f"""
        <style>
        .side-by-side-diff {{
            border: 1px solid #444;
            border-radius: 6px;
            overflow: auto;
            font-family: monospace;
            font-size: 0.85rem;
        }}
        .side-by-side-diff table {{ border-collapse: collapse; width: 100%; }}
        .side-by-side-diff th {{
            background: #262730;
            padding: 0.45rem;
            text-align: left;
            position: sticky;
            top: 0;
        }}
        .side-by-side-diff td {{ padding: 0.15rem 0.45rem; white-space: pre; }}
        .side-by-side-diff .line-number {{
            color: #888;
            text-align: right;
            user-select: none;
            border-right: 1px solid #444;
            width: 2.5rem;
        }}
        .side-by-side-diff .removed {{ background: #512b2b; }}
        .side-by-side-diff .added {{ background: #254b32; }}
        .side-by-side-diff .empty {{ background: #1d1d23; }}
        </style>
        <div class="side-by-side-diff">
          <table>
            <thead><tr><th colspan="2">Current model</th>
                   <th colspan="2">Corrected model</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

duckdb_error = _check_duckdb_available()
if duckdb_error:
    st.warning(duckdb_error)

if st.button("Run diagnostic, investigation & correction", type="primary"):
    lock_error = _check_duckdb_available()
    if lock_error:
        st.error(lock_error)
        st.stop()
    if reset_first:
        reset_scenario()
    activate_scenario(scenario_id)
    result = run_dbt_build()
    if result.success:
        st.error("dbt build succeeded — scenario did not produce a failure.")
    else:
        run_results_path = settings.dbt_dir / "target" / "run_results.json"
        if not run_results_path.exists():
            diagnostic = extract_dbt_error_text(
                f"{result.stdout}\n{result.stderr}",
                command_executed=result.command,
            )
        else:
            diagnostic = run_diagnostic()
        if not diagnostic.has_errors:
            st.error("dbt build failed but no error nodes found in the diagnostic.")
        else:
            diagnostic = prioritize_failed_nodes_for_scenario(diagnostic, scenario_id)
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
            with st.spinner("Running investigation..."):
                record = _run_async(run_investigation(incident_id))
            st.session_state["record"] = record
            if record.investigation_output:
                st.subheader("Investigation")
                st.write(record.investigation_output)
            if record.status == IncidentStatus.INVESTIGATED:
                with st.spinner("Generating correction..."):
                    record = _run_async(run_correction(incident_id))
                st.session_state["record"] = record
    st.rerun()

incident_id = st.session_state.get("incident_id") or get_current_incident_id()
if incident_id:
    st.subheader(f"Incident {incident_id}")
    record = load_incident(incident_id)
    record = st.session_state.get("record") or record

    with st.expander("Diagnostic", expanded=False):
        st.json(record.diagnostic.model_dump())

    infra_message = _infrastructure_error_message(record.diagnostic)
    if infra_message:
        st.error(infra_message)

    with st.expander("Investigation", expanded=True):
        st.write(record.investigation_output or "(not run)")

    with st.expander("Proposed patch", expanded=True):
        if record.patch:
            st.write(record.patch.summary)
            st.caption(f"File: `{record.patch.file_path}`")
            _render_side_by_side_diff(
                record.patch.original_content,
                record.patch.patched_content,
            )
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
