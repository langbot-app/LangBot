#!/usr/bin/env python3
"""Fail CI when a service job can start Core without disabling product telemetry."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

SERVICE_MARKERS = ('regression_ci', 'LANGBOT_DATA_ROOT', 'SPACE__URL')
KNOWN_SERVICE_WORKFLOWS = {
    'artifact-accelerated-soak.yml',
    'artifact-qa.yml',
    'core-smoke.yml',
    'daily-endurance.yml',
    'persistence-acceptance.yml',
    'run-tests.yml',
}
KNOWN_SERVICE_JOBS = {
    'persistence-acceptance.yml': {'persistence-runtime'},
    'run-tests.yml': {'e2e'},
}
ENV_NAME = 'SPACE__DISABLE_TELEMETRY'


def _text(value: object) -> str:
    return yaml.safe_dump(value, sort_keys=True)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() == 'true'


def _falsey(value: object) -> bool:
    return str(value).strip().lower() in {'false', '0', 'no'}


def _env(value: object) -> dict[object, object]:
    return value if isinstance(value, dict) else {}


def _has_marker(value: object) -> bool:
    return any(marker in _text(value) for marker in SERVICE_MARKERS)


def _service_steps(job: object) -> list[tuple[int, dict[object, object]]]:
    if not isinstance(job, dict) or not isinstance(job.get('steps'), list):
        return []
    return [(index, step) for index, step in enumerate(job['steps']) if isinstance(step, dict) and _has_marker(step)]


def _job_without_steps(job: object) -> object:
    if not isinstance(job, dict):
        return job
    return {key: value for key, value in job.items() if key != 'steps'}


def _effective_value(
    workflow_env: object,
    job_env: object,
    step_env: object = None,
) -> object:
    value = _env(workflow_env).get(ENV_NAME)
    value = _env(job_env).get(ENV_NAME, value)
    return _env(step_env).get(ENV_NAME, value)


def _check_value(workflow: Path, scope: str, value: object) -> str | None:
    if _falsey(value):
        return f'{workflow} {scope}: telemetry is explicitly enabled'
    if not _truthy(value):
        return f'{workflow} {scope}: missing {ENV_NAME}=true'
    return None


def check_workflows(workflows_root: Path) -> list[str]:
    """Return job-scoped violations for Core/service CI lanes."""
    violations: list[str] = []
    for workflow in sorted(workflows_root.glob('*.y*ml')):
        data = yaml.safe_load(workflow.read_text(encoding='utf-8')) or {}
        jobs = data.get('jobs') if isinstance(data, dict) else None
        if not isinstance(jobs, dict):
            if workflow.name in KNOWN_SERVICE_WORKFLOWS:
                violations.append(f'{workflow}: no jobs found')
            continue

        workflow_env = data.get('env')
        known_jobs = KNOWN_SERVICE_JOBS.get(workflow.name, set())
        for name, job in jobs.items():
            steps = _service_steps(job)
            is_service_job = name in known_jobs or _has_marker(_job_without_steps(job))
            if not is_service_job and not steps:
                continue

            job_env = job.get('env') if isinstance(job, dict) else {}
            if steps:
                for index, step in steps:
                    violation = _check_value(
                        workflow,
                        f'job {name} step {index}',
                        _effective_value(workflow_env, job_env, step.get('env')),
                    )
                    if violation:
                        violations.append(violation)
                continue

            violation = _check_value(
                workflow,
                f'job {name}',
                _effective_value(workflow_env, job_env),
            )
            if violation:
                violations.append(violation)
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1] / '.github' / 'workflows'
    violations = check_workflows(root)
    if violations:
        print('\n'.join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
