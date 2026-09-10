"""Deterministic fix pipeline: apply patch, validate, create PR."""

from __future__ import annotations

import subprocess

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings
from dbt_failure_pipeline.core.exceptions import PatchNotAllowedError
from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
from dbt_failure_pipeline.core.state import load_incident, save_incident
from dbt_failure_pipeline.deterministic.execution import run_dbt_build, run_dbt_compile, run_dbt_test
from dbt_failure_pipeline.github.pr import create_pull_request
from dbt_failure_pipeline.tools.patch_tools import _is_allowed


def apply_patch(file_path: str, patched_content: str) -> None:
    target = (PROJECT_ROOT / file_path).resolve()
    if not _is_allowed(target):
        raise PatchNotAllowedError(f"Cannot patch {file_path}")
    target.write_text(patched_content, encoding="utf-8")


def prepare_branch_from_main(branch_name: str) -> None:
    """Recreate the fix branch from the latest local main branch."""
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "push", "origin", "--delete", branch_name],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", branch_name, "main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def create_commit(message: str, file_path: str) -> None:
    subprocess.run(["git", "add", "--", file_path], cwd=PROJECT_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def push_branch(branch_name: str) -> None:
    subprocess.run(
        ["git", "push", "--set-upstream", "origin", branch_name],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def run_fix_pipeline(incident_id: str, human_approved: bool = True) -> InvestigationRecord:
    record = load_incident(incident_id)
    if not human_approved:
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        return record

    if not record.patch or not record.patch.patched_content:
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        return record

    record.status = IncidentStatus.FIXING
    save_incident(record)

    branch = f"fix/dbt-{incident_id.lower()}"
    try:
        prepare_branch_from_main(branch)
    except subprocess.CalledProcessError:
        record.status = IncidentStatus.NEEDS_HUMAN
        record.metadata["git_error"] = "Unable to prepare fix branch from main"
        save_incident(record)
        return record

    apply_patch(record.patch.file_path, record.patch.patched_content)

    compile_result = run_dbt_compile()
    test_result = run_dbt_test()
    record.validation_passed = compile_result.success and test_result.success

    if not record.validation_passed and settings.max_fix_retries >= 1:
        build_result = run_dbt_build()
        record.validation_passed = build_result.success
        if not record.validation_passed:
            record.status = IncidentStatus.NEEDS_HUMAN
            record.metadata["validation_error"] = build_result.stderr[-2000:]
            save_incident(record)
            return record

    if record.validation_passed:
        msg = f"fix(dbt): {record.patch.summary} [{incident_id}]"
        try:
            create_commit(msg, record.patch.file_path)
            push_branch(branch)
            pr_body = _build_pr_body(record)
            pr_url = create_pull_request(
                title=f"fix(dbt): {record.patch.summary}",
                body=pr_body,
            )
            record.pr_url = pr_url
            record.status = IncidentStatus.PR_CREATED
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            record.metadata["pr_error"] = str(e)
            record.status = IncidentStatus.NEEDS_HUMAN
    else:
        record.status = IncidentStatus.NEEDS_HUMAN

    save_incident(record)
    return record


def _build_pr_body(record: InvestigationRecord) -> str:
    rca = record.rca.root_cause if record.rca else "See investigation output"
    evidence = "\n".join(f"- {e}" for e in (record.rca.evidence if record.rca else [])[:5])
    return f"""## Summary
{record.patch.summary if record.patch else 'N/A'}

## Root cause
{rca}

## Evidence
{evidence}

## Affected models
{', '.join(record.rca.affected_models if record.rca else [])}

## Proposed fix
```
{record.patch.diff_unified if record.patch else ''}
```

## Tests executed
- dbt compile
- dbt test

## Agent confidence
{record.rca.confidence if record.rca else 'N/A'}

## Limitations
Human review required before merge.
"""
