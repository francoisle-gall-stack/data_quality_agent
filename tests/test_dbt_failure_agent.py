"""Tests for dbt failure diagnosis and investigation context."""

import json

import pytest

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.exceptions import PatchNotAllowedError
from dbt_failure_pipeline.core.models import ErrorCategory
from dbt_failure_pipeline.deterministic.diagnostic import (
    extract_dbt_error_text,
    extract_dbt_errors,
    run_diagnostic,
)
from dbt_failure_pipeline.deterministic.investigation.context import build_investigation_context
from dbt_failure_pipeline.deterministic.investigation.context.manifest import (
    load_filtered_manifest,
)
from dbt_failure_pipeline.evaluation.classification import classify_error
from dbt_failure_pipeline.evaluation.metrics import classifications_match, failure_count_match
from dbt_failure_pipeline.tools.model_tools import get_dbt_macro, get_dbt_model
from dbt_failure_pipeline.tools.compiled_sql_tool import get_dbt_compiled_sql
from dbt_failure_pipeline.tools.diagnostic_tool import get_dbt_diagnostic
from dbt_failure_pipeline.tools.git_history_tool import get_dbt_git_history
from dbt_failure_pipeline.tools.macros_tool import get_dbt_macros
from dbt_failure_pipeline.tools.manifest_tool import get_dbt_manifest
from dbt_failure_pipeline.tools.models_tool import get_dbt_models
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


def test_get_dbt_macro_returns_source_sql(tmp_path, monkeypatch):
    dbt_dir = tmp_path / "dbt"
    macro_path = dbt_dir / "macros" / "order_revenue.sql"
    macro_path.parent.mkdir(parents=True)
    macro_path.write_text(
        "{% macro order_revenue_expression(a, b) %}{{ a }} * {{ b }}{% endmacro %}",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "dbt_dir", dbt_dir)

    result = json.loads(get_dbt_macro("order_revenue"))

    assert result["path"] == "dbt/macros/order_revenue.sql"
    assert "order_revenue_expression" in result["sql"]


def test_context_tools_collect_all_sources(tmp_path, monkeypatch):
    dbt_dir = tmp_path / "dbt"
    target = dbt_dir / "target"
    model_dir = dbt_dir / "models" / "intermediate"
    model_dir.mkdir(parents=True)
    target.mkdir()
    (model_dir / "orders.sql").write_text("select 1", encoding="utf-8")
    (dbt_dir / "macros").mkdir()
    (dbt_dir / "macros" / "revenue.sql").write_text(
        "{% macro revenue() %}1{% endmacro %}", encoding="utf-8"
    )
    diagnostic = {
        "failed_nodes": [{"unique_id": "model.project.orders"}],
    }
    manifest = {
        "nodes": {
            "model.project.orders": {
                "unique_id": "model.project.orders",
                "resource_type": "model",
                "name": "orders",
                "original_file_path": "models/intermediate/orders.sql",
                "compiled_path": "target/compiled/project/models/orders.sql",
                "depends_on": {"nodes": []},
                "raw_code": "select 1",
            }
        }
    }
    (target / "diagnostic.json").write_text(json.dumps(diagnostic), encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    compiled = target / "compiled" / "project" / "models"
    compiled.mkdir(parents=True)
    (compiled / "orders.sql").write_text("select 1", encoding="utf-8")
    monkeypatch.setattr(settings, "dbt_dir", dbt_dir)

    assert json.loads(get_dbt_diagnostic()) == diagnostic
    assert "model.project.orders" in json.loads(get_dbt_manifest())["nodes"]
    assert json.loads(get_dbt_compiled_sql())["model.project.orders"]["sql"] == "select 1"
    assert "model.project.orders" in json.loads(get_dbt_git_history())
    assert json.loads(get_dbt_models("orders"))["orders"]["sql"] == "select 1"
    assert "revenue" in json.loads(get_dbt_macros())


def test_filtered_manifest_contains_transitive_lineage_for_multiple_failures(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    manifest = {
        "nodes": {
            "model.project.upstream": {
                "unique_id": "model.project.upstream",
                "resource_type": "model",
                "name": "upstream",
                "depends_on": {"nodes": []},
                "raw_code": "select 1",
            },
            "model.project.failed_a": {
                "unique_id": "model.project.failed_a",
                "resource_type": "model",
                "name": "failed_a",
                "depends_on": {"nodes": ["model.project.upstream"]},
                "raw_code": "select * from upstream",
            },
            "model.project.failed_b": {
                "unique_id": "model.project.failed_b",
                "resource_type": "model",
                "name": "failed_b",
                "depends_on": {"nodes": ["model.project.upstream"]},
                "raw_code": "select * from upstream",
            },
            "model.project.downstream": {
                "unique_id": "model.project.downstream",
                "resource_type": "model",
                "name": "downstream",
                "depends_on": {
                    "nodes": ["model.project.failed_a", "model.project.failed_b"]
                },
                "raw_code": "select * from failed_a",
            },
            "model.project.unrelated": {
                "unique_id": "model.project.unrelated",
                "resource_type": "model",
                "name": "unrelated",
                "depends_on": {"nodes": []},
            },
            "source.project.raw": {
                "unique_id": "source.project.raw",
                "resource_type": "source",
                "name": "raw",
                "depends_on": {"nodes": []},
            },
        }
    }
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = load_filtered_manifest(
        target, ["model.project.failed_a", "model.project.failed_b"]
    )

    assert set(result["nodes"]) == {
        "model.project.upstream",
        "model.project.failed_a",
        "model.project.failed_b",
        "model.project.downstream",
    }
    assert result["lineage"]["upstream_model_count"] == 1
    assert result["lineage"]["downstream_model_count"] == 1
    assert result["lineage"]["upstream_models"] == ["model.project.upstream"]
    assert result["lineage"]["downstream_models"] == ["model.project.downstream"]
    assert result["nodes"]["model.project.failed_a"]["raw_code"] == (
        "select * from upstream"
    )


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


def test_multi_failure_diagnostic_is_order_insensitive(tmp_path):
    run_results_path = tmp_path / "run_results.json"
    run_results_path.write_text(
        json.dumps(
            {
                "args": {"invocation_command": "dbt build"},
                "results": [
                    {
                        "unique_id": "test.project.orders_unique",
                        "status": "fail",
                        "message": "Got 2 results, configured to fail if != 0",
                    },
                    {
                        "unique_id": "model.project.orders",
                        "status": "error",
                        "message": "Binder Error: Referenced column missing not found",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    diagnostic = extract_dbt_errors(run_results_path)

    ground_truth = {
        "failures": [
            {"classification": {"error_type": "schema_change"}},
            {"classification": {"error_type": "dbt_test_failure"}},
        ]
    }
    assert len(diagnostic.failed_nodes) == 2
    assert failure_count_match(diagnostic, ground_truth)
    assert classifications_match(diagnostic, ground_truth)


def test_diagnostic_fallback_handles_pre_run_compilation_error():
    diagnostic = extract_dbt_error_text(
        "Compilation Error\nEnv var required but not provided: 'SC026_REQUIRED'"
    )

    assert diagnostic.has_errors
    assert diagnostic.failed_nodes[0].error_message.startswith("Compilation Error")
