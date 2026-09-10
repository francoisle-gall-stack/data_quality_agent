"""Scenario activation and reset."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from dbt_failure_pipeline.core.config import PROJECT_ROOT, RUNTIME_DIR, SCENARIOS_DIR
from dbt_failure_pipeline.core.exceptions import ScenarioNotFoundError

BACKUP_DIR = RUNTIME_DIR / "backup"
ACTIVE_FILE = RUNTIME_DIR / "active_scenario.txt"


def list_scenarios() -> list[str]:
    return sorted(
        p.name for p in SCENARIOS_DIR.iterdir() if p.is_dir() and p.name.startswith("SC")
    )


def get_scenario_info(scenario_id: str) -> dict[str, str]:
    """Return the human-readable metadata for a scenario."""
    manifest = _load_manifest(scenario_id)
    name = str(manifest.get("name", scenario_id))
    description = str(manifest.get("description") or name)
    return {
        "scenario_id": scenario_id,
        "name": name,
        "description": description,
    }


def _load_manifest(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / scenario_id / "manifest.yaml"
    if not path.exists():
        raise ScenarioNotFoundError(f"Scenario {scenario_id} not found at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def activate_scenario(scenario_id: str) -> dict:
    manifest = _load_manifest(scenario_id)
    backup_path = BACKUP_DIR / scenario_id
    backup_path.mkdir(parents=True, exist_ok=True)

    patched: list[str] = []
    for rel_path in manifest.get("patch_files", []):
        src = SCENARIOS_DIR / scenario_id / "patches" / Path(rel_path).name
        if not src.exists():
            src = SCENARIOS_DIR / scenario_id / "patches" / rel_path
        target = PROJECT_ROOT / rel_path
        if target.exists():
            shutil.copy2(target, backup_path / rel_path.replace("/", "__"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        patched.append(rel_path)

    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(scenario_id, encoding="utf-8")
    return {"scenario_id": scenario_id, "patched_files": patched}


def reset_scenario() -> dict:
    if not ACTIVE_FILE.exists():
        return {"reset": False, "reason": "no active scenario"}
    scenario_id = ACTIVE_FILE.read_text(encoding="utf-8").strip()
    backup_path = BACKUP_DIR / scenario_id
    if not backup_path.exists():
        ACTIVE_FILE.unlink(missing_ok=True)
        return {"reset": False, "reason": "no backup found"}

    manifest = _load_manifest(scenario_id)
    restored: list[str] = []
    for rel_path in manifest.get("patch_files", []):
        backup_file = backup_path / rel_path.replace("/", "__")
        target = PROJECT_ROOT / rel_path
        if backup_file.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, target)
            restored.append(rel_path)
        elif target.exists():
            target.unlink()
            restored.append(rel_path)

    ACTIVE_FILE.unlink(missing_ok=True)
    return {"reset": True, "scenario_id": scenario_id, "restored_files": restored}


def get_active_scenario() -> str | None:
    return ACTIVE_FILE.read_text(encoding="utf-8").strip() if ACTIVE_FILE.exists() else None
