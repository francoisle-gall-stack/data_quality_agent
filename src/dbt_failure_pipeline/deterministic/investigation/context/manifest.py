"""Récupération et filtrage déterministes du manifest dbt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_filtered_manifest(
    target_dir: Path, failed_ids: str | list[str]
) -> dict[str, Any]:
    """Load only failed nodes and their transitive upstream/downstream lineage."""
    path = target_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Artefact requis introuvable : {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    all_nodes: dict[str, Any] = {
        **manifest.get("nodes", {}),
        **manifest.get("sources", {}),
    }
    if isinstance(failed_ids, str):
        failed_ids = [failed_ids]
    missing = [node_id for node_id in failed_ids if node_id not in all_nodes]
    if missing:
        raise ValueError(f"Nœuds en échec absents de manifest.json : {', '.join(missing)}")

    children: dict[str, list[str]] = {node_id: [] for node_id in all_nodes}
    for node_id, node in all_nodes.items():
        for parent_id in node.get("depends_on", {}).get("nodes", []):
            if parent_id in children:
                children[parent_id].append(node_id)

    def walk(start_ids: list[str], graph: dict[str, list[str]]) -> set[str]:
        visited: set[str] = set()
        pending = list(start_ids)
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            pending.extend(graph.get(node_id, []))
        return visited

    parents = {
        node_id: [
            parent_id
            for parent_id in node.get("depends_on", {}).get("nodes", [])
            if parent_id in all_nodes
        ]
        for node_id, node in all_nodes.items()
    }
    upstream_ids = walk(list(failed_ids), parents) - set(failed_ids)
    downstream_ids = walk(list(failed_ids), children) - set(failed_ids)
    selected_ids = set(failed_ids) | upstream_ids | downstream_ids

    model_ids = {
        node_id for node_id, node in all_nodes.items() if node.get("resource_type") == "model"
    }
    upstream_models = sorted((upstream_ids & model_ids) - set(failed_ids))
    downstream_models = sorted((downstream_ids & model_ids) - set(failed_ids))
    failed_model_ids = sorted(set(failed_ids) & model_ids)

    def distances(start_id: str, graph: dict[str, list[str]]) -> dict[str, int]:
        result: dict[str, int] = {}
        pending = [(start_id, 0)]
        while pending:
            node_id, distance = pending.pop(0)
            if node_id in result and result[node_id] <= distance:
                continue
            result[node_id] = distance
            pending.extend((child, distance + 1) for child in graph.get(node_id, []))
        return result

    lineage_by_failure = {}
    for failed_id in failed_ids:
        upstream = distances(failed_id, parents)
        downstream = distances(failed_id, children)
        lineage_by_failure[failed_id] = {
            "upstream": [
                {"unique_id": node_id, "lineage_level": -distance}
                for node_id, distance in sorted(upstream.items())
                if node_id != failed_id and node_id in model_ids
            ],
            "downstream": [
                {"unique_id": node_id, "lineage_level": distance}
                for node_id, distance in sorted(downstream.items())
                if node_id != failed_id and node_id in model_ids
            ],
        }

    compact_nodes = {}
    for node_id in sorted(selected_ids):
        node = all_nodes[node_id]
        compact_nodes[node_id] = {
            key: node[key]
            for key in (
                "unique_id",
                "resource_type",
                "name",
                "package_name",
                "path",
                "original_file_path",
                "compiled_path",
                "raw_code",
                "depends_on",
                "config",
                "columns",
            )
            if key in node
        }

    return {
        "nodes": compact_nodes,
        "lineage": {
            "failed_models": failed_model_ids,
            "upstream_models": upstream_models,
            "downstream_models": downstream_models,
            "upstream_model_count": len(upstream_models),
            "downstream_model_count": len(downstream_models),
            "by_failure": lineage_by_failure,
        },
    }
