"""Récupération et filtrage déterministes du manifest dbt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_filtered_manifest(target_dir: Path, failed_id: str) -> dict[str, Any]:
    """Charge manifest.json et conserve l'échec et ses dépendances directes."""
    path = target_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Artefact requis introuvable : {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    all_nodes: dict[str, Any] = {
        **manifest.get("nodes", {}),
        **manifest.get("sources", {}),
    }
    failed_node = all_nodes.get(failed_id)
    if not failed_node:
        raise ValueError(f"Le nœud en échec est absent de manifest.json : {failed_id}")

    parent_ids = failed_node.get("depends_on", {}).get("nodes", [])
    selected_ids = [failed_id, *[node_id for node_id in parent_ids if node_id in all_nodes]]
    return {"nodes": {node_id: all_nodes[node_id] for node_id in selected_ids}}
