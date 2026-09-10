"""In-memory / file-backed incident state."""

from __future__ import annotations

import json
import re
from pathlib import Path

from dbt_failure_pipeline.core.config import INCIDENTS_DIR
from dbt_failure_pipeline.core.exceptions import IncidentNotFoundError
from dbt_failure_pipeline.core.models import InvestigationRecord

_INCIDENTS: dict[str, InvestigationRecord] = {}
_FILE_PATH_FROM_MESSAGE = re.compile(r"\((models[/\\][^)]+)\)")


def _migrate_legacy_incident(data: dict) -> dict:
    """Convert pre-refactor incidents (context + diagnostic=null) to DbtDiagnostic."""
    if data.get("diagnostic"):
        return data

    context = data.get("context")
    if not context:
        return data

    failed_node = context.get("failed_node", "")
    parts = failed_node.split(".")
    node_type = parts[0] if parts else "unknown"
    node_name = parts[-1] if len(parts) > 1 else failed_node
    error_message = context.get("error_message", "")
    file_path = context.get("file_path", "")
    if not file_path and error_message:
        match = _FILE_PATH_FROM_MESSAGE.search(error_message)
        if match:
            file_path = match.group(1)

    data["diagnostic"] = {
        "command_executed": context.get("dbt_command", "Inconnue"),
        "has_errors": True,
        "failed_nodes": [
            {
                "node_type": node_type,
                "unique_id": failed_node,
                "node_name": node_name,
                "file_path": file_path,
                "error_message": error_message,
            }
        ],
    }
    data.pop("context", None)
    data.pop("diagnostic_output", None)
    return data


def _load_record_from_path(path: Path) -> InvestigationRecord:
    raw = json.loads(path.read_text(encoding="utf-8"))
    migrated = _migrate_legacy_incident(raw)
    return InvestigationRecord.model_validate(migrated)


def save_incident(record: InvestigationRecord) -> None:
    _INCIDENTS[record.incident_id] = record
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = INCIDENTS_DIR / f"{record.incident_id}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def load_incident(incident_id: str) -> InvestigationRecord:
    if incident_id in _INCIDENTS:
        return _INCIDENTS[incident_id]
    path = INCIDENTS_DIR / f"{incident_id}.json"
    if not path.exists():
        raise IncidentNotFoundError(f"Incident {incident_id} not found")
    record = _load_record_from_path(path)
    _INCIDENTS[incident_id] = record
    return record


def list_incidents() -> list[InvestigationRecord]:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    records = list(_INCIDENTS.values())
    for path in INCIDENTS_DIR.glob("*.json"):
        if path.stem not in _INCIDENTS:
            records.append(_load_record_from_path(path))
    return sorted(records, key=lambda r: r.created_at, reverse=True)


def set_current_incident_id(incident_id: str) -> None:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    (INCIDENTS_DIR / "current.txt").write_text(incident_id, encoding="utf-8")


def get_current_incident_id() -> str | None:
    path = INCIDENTS_DIR / "current.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None
