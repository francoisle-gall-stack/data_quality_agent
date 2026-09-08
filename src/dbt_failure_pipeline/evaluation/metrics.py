"""Evaluation metrics for dbt failure scenarios."""

from __future__ import annotations

from dbt_failure_pipeline.core.models import DbtDiagnostic, InvestigationRecord
from dbt_failure_pipeline.evaluation.classification import classify_diagnostic


def classification_match(diagnostic: DbtDiagnostic, expected_type: str) -> bool:
    return classify_diagnostic(diagnostic).value == expected_type


def root_cause_file_match(record: InvestigationRecord, expected_file: str) -> bool:
    if record.patch and record.patch.file_path:
        return expected_file.replace("\\", "/") in record.patch.file_path.replace("\\", "/")
    if record.rca and record.rca.proposed_fix:
        return expected_file in record.rca.proposed_fix
    return expected_file in (record.investigation_output or "")


def compile_test_success(record: InvestigationRecord) -> bool:
    return record.validation_passed is True
