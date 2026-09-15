"""Deterministic routing for dashboard questions."""

from dataclasses import dataclass, field


@dataclass
class Intent:
    name: str
    entities: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)


def classify_intent(question: str, chart_id: str | None = None) -> Intent:
    text = question.lower()
    if any(x in text for x in ("calcul", "défini", "definition", "ca ", "chiffre d'affaires")):
        name, tools = "metric_definition", ["get_dbt_schema_yml", "get_dbt_models", "get_dbt_manifest"]
    elif any(x in text for x in ("quelle table", "source", "alimente", "alimenté")):
        name, tools = "chart_source", ["get_dbt_manifest", "get_dbt_models"]
    elif any(x in text for x in ("pourquoi", "anomal", "chute", "baisse", "hausse")):
        name, tools = "anomaly_explanation", ["get_anomaly_history", "run_sql", "get_metric_history"]
    elif any(x in text for x in ("vient", "lineage", "origine", "d'où")):
        name, tools = "lineage", ["get_dbt_manifest", "get_dbt_models"]
    else:
        name, tools = "data_exploration", ["run_sql", "get_schema"]
    return Intent(name=name, entities={"chart_id": chart_id or ""}, tools=tools)
