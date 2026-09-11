"""Evaluation metrics for dbt failure scenarios."""

from __future__ import annotations

from collections import Counter
from typing import Any

from dbt_failure_pipeline.core.models import DbtDiagnostic, InvestigationRecord
from dbt_failure_pipeline.evaluation.classification import (
    classify_diagnostic,
    normalize_error_type,
)


def classification_match(diagnostic: DbtDiagnostic, expected_type: str) -> bool:
    return classify_diagnostic(diagnostic).value == normalize_error_type(expected_type)


def _observed_categories(diagnostic: DbtDiagnostic) -> list[str]:
    if diagnostic.failures:
        return [f.category for f in diagnostic.failures if f.category]
    return [
        node.category
        or classify_diagnostic(
            DbtDiagnostic(
                command_executed=diagnostic.command_executed,
                has_errors=True,
                failed_nodes=[node],
            )
        ).value
        for node in diagnostic.failed_nodes
    ]


def _expected_failures(ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
    failures = ground_truth.get("failures")
    if failures:
        return failures
    return [
        {
            "classification": {
                "error_type": normalize_error_type(ground_truth.get("error_type", ""))
            },
            "expected_fixes": [ground_truth.get("expected_fix", {})],
        }
    ]


def failure_count_match(diagnostic: DbtDiagnostic, ground_truth: dict[str, Any]) -> bool:
    expected = _expected_failures(ground_truth)
    return len(diagnostic.failed_nodes) == len(expected)


def classifications_match(diagnostic: DbtDiagnostic, ground_truth: dict[str, Any]) -> bool:
    expected = [
        normalize_error_type(item.get("classification", {}).get("error_type", ""))
        or item.get("error_type", "")
        for item in _expected_failures(ground_truth)
    ]
    observed = _observed_categories(diagnostic)
    return Counter(observed) == Counter(filter(None, expected))


def root_cause_file_match(record: InvestigationRecord, expected_file: str) -> bool:
    if record.patch and record.patch.file_path:
        return expected_file.replace("\\", "/") in record.patch.file_path.replace("\\", "/")
    if record.rca and record.rca.proposed_fix:
        return expected_file in record.rca.proposed_fix
    return expected_file in (record.investigation_output or "")


def expected_fix_files_match(record: InvestigationRecord, ground_truth: dict[str, Any]) -> bool:
    expected = {
        fix.get("file", "").replace("\\", "/")
        for item in _expected_failures(ground_truth)
        for fix in item.get("expected_fixes", [])
        if fix.get("file")
    }
    if not expected:
        return False
    observed = {
        patch.file_path.replace("\\", "/")
        for patch in record.patches
        if patch.file_path
    }
    if record.patch and record.patch.file_path:
        observed.add(record.patch.file_path.replace("\\", "/"))
    return expected.issubset(observed)


def compile_test_success(record: InvestigationRecord) -> bool:
    return record.validation_passed is True
