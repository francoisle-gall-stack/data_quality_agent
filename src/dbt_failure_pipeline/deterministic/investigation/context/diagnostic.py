"""Récupération déterministe du diagnostic dbt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_diagnostic(target_dir: Path) -> dict[str, Any]:
    """Charge le diagnostic produit par l'étape de diagnostic dbt."""
    path = target_dir / "diagnostic.json"
    if not path.exists():
        raise FileNotFoundError(f"Artefact requis introuvable : {path}")
    diagnostic = json.loads(path.read_text(encoding="utf-8"))
    if not diagnostic.get("failed_nodes"):
        raise ValueError("diagnostic.json ne contient aucun nœud en échec")
    return diagnostic


def get_failed_nodes(diagnostic: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all failed nodes and validate their identifiers."""
    failed_nodes = diagnostic.get("failed_nodes", [])
    if not failed_nodes:
        raise ValueError("diagnostic.json ne contient aucun nœud en échec")
    for node in failed_nodes:
        if not node.get("unique_id"):
            raise ValueError("Un nœud en échec n'a pas de unique_id")
    return failed_nodes


def get_failed_node(diagnostic: dict[str, Any]) -> dict[str, Any]:
    """Return the first failed node for backwards compatibility."""
    return get_failed_nodes(diagnostic)[0]
