"""Tests for dbt failure diagnosis and investigation context."""

import json

import pytest

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.exceptions import PatchNotAllowedError
from dbt_failure_pipeline.core.models import ErrorCategory
from dbt_failure_pipeline.deterministic.diagnostic import extract_dbt_errors, run_diagnostic
from dbt_failure_pipeline.deterministic.investigation.context import build_investigation_context
from dbt_failure_pipeline.evaluation.classification import classify_error
from dbt_failure_pipeline.tools.model_tools import get_dbt_model
from dbt_failure_pipeline.tools.patch_tools import propose_patch


def test_classify_schema_change():
    assert classify_error("Binder Error: Referenced column customer_segment not found") == (
        ErrorCategory.SCHEMA_CHANGE
    )


def test_classify_sql_compilation():
    assert classify_error("Parser Error: syntax error at or near SELEC") == (
        ErrorCategory.SQL_COMPILATION
    )


def test_propose_patch_allowlisted():
    model = settings.dbt_dir / "models" / "1_intermediate" / "int_orders.sql"
    original = model.read_text(encoding="utf-8")
    patched = original.replace("customer_type", "customer_type AS ct")
    out = json.loads(propose_patch("dbt/models/1_intermediate/int_orders.sql", patched, "test"))
    assert out["status"] == "proposed"


def test_propose_patch_rejects_outside_allowlist():
    with pytest.raises(PatchNotAllowedError):
        propose_patch("README.md", "hack", "bad")


def test_get_dbt_model_returns_source_sql(tmp_path, monkeypatch):
    dbt_dir = tmp_path / "dbt"
    model_path = dbt_dir / "models" / "intermediate" / "orders.sql"
    model_path.parent.mkdir(parents=True)
    model_path.write_text("select * from {{ ref('stg_orders') }}", encoding="utf-8")
    monkeypatch.setattr(settings, "dbt_dir", dbt_dir)

    result = json.loads(get_dbt_model("orders"))

    assert result["path"] == "dbt/models/intermediate/orders.sql"
    assert result["sql"] == "select * from {{ ref('stg_orders') }}"


def test_context_filters_manifest_and_loads_compiled_sql(tmp_path, monkeypatch):
    target = tmp_path / "target"
    compiled = target / "compiled" / "project" / "models"
    compiled.mkdir(parents=True)
    diagnostic = {
        "failed_nodes": [
            {
                "unique_id": "model.project.orders",
                "file_path": "models/orders.sql",
            }
        ]
    }
    manifest = {
        "nodes": {
            "model.project.orders": {
                "unique_id": "model.project.orders",
                "resource_type": "model",
                "original_file_path": "models/orders.sql",
                "compiled_path": "target/compiled/project/models/orders.sql",
                "depends_on": {"nodes": ["model.project.customers", "source.project.raw"]},
            },
            "model.project.customers": {
                "unique_id": "model.project.customers",
                "resource_type": "model",
                "compiled_path": "target/compiled/project/models/customers.sql",
            },
            "model.project.unrelated": {"unique_id": "model.project.unrelated"},
        },
        "sources": {
            "source.project.raw": {
                "unique_id": "source.project.raw",
                "resource_type": "source",
                "compiled_path": "target/compiled/project/models/raw.sql",
            }
        },
    }
    (target / "diagnostic.json").write_text(json.dumps(diagnostic), encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (compiled / "orders.sql").write_text("select * from orders", encoding="utf-8")
    (compiled / "customers.sql").write_text("select * from customers", encoding="utf-8")
    (compiled / "raw.sql").write_text("select * from raw", encoding="utf-8")
    monkeypatch.setattr(settings, "dbt_dir", tmp_path)

    context = build_investigation_context()

    assert set(context.manifest["nodes"]) == {
        "model.project.orders",
        "model.project.customers",
        "source.project.raw",
    }
    assert context.compiled_sql["model.project.customers"]["sql"] == "select * from customers"
    assert "model.project.unrelated" not in context.manifest["nodes"]


def test_extract_dbt_errors_writes_diagnostic(tmp_path):
    run_results = {
        "args": {"invocation_command": "dbt build"},
        "results": [
            {
                "unique_id": "model.project.orders",
                "status": "error",
                "message": "Runtime Error in model orders (models/orders.sql)",
            }
        ],
    }
    run_results_path = tmp_path / "run_results.json"
    output_path = tmp_path / "diagnostic.json"
    run_results_path.write_text(json.dumps(run_results), encoding="utf-8")

    diagnostic = extract_dbt_errors(run_results_path, output_path=output_path)

    assert diagnostic.has_errors
    assert output_path.exists()


def test_run_diagnostic_writes_file(tmp_path, monkeypatch):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "run_results.json").write_text(
        json.dumps(
            {
                "args": {"invocation_command": "dbt build"},
                "results": [
                    {
                        "unique_id": "model.project.orders",
                        "status": "error",
                        "message": "Runtime Error in model orders (models/orders.sql)",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "dbt_dir", tmp_path)

    assert run_diagnostic().has_errors
    assert (target_dir / "diagnostic.json").exists()
