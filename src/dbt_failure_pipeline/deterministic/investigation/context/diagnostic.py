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


def get_failed_node(diagnostic: dict[str, Any]) -> dict[str, Any]:
    """Retourne le premier nœud en échec et vérifie son identifiant."""
    failed_node = diagnostic["failed_nodes"][0]
    if not failed_node.get("unique_id"):
        raise ValueError("Le nœud en échec n'a pas de unique_id")
    return failed_node
