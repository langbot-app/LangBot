#!/usr/bin/env python3
"""Fail CI when a service job/action can start Core without disabling telemetry.

Local reusable workflow callees are checked recursively.
"""

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
    'p0-acceptance.yml',
    'persistence-acceptance.yml',
    'run-tests.yml',
}
KNOWN_SERVICE_JOBS = {
    'p0-acceptance.yml': {'permissions'},
    'persistence-acceptance.yml': {'persistence-runtime'},
    'run-tests.yml': {'e2e'},
}
ENV_NAME = 'SPACE__DISABLE_TELEMETRY'
LOCAL_WORKFLOW_PREFIX = './.github/workflows/'


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


def _effective_value(workflow_env: object, job_env: object, step_env: object = None) -> object:
    value = _env(workflow_env).get(ENV_NAME)
    value = _env(job_env).get(ENV_NAME, value)
    return _env(step_env).get(ENV_NAME, value)


def _check_value(workflow: Path, scope: str, value: object) -> str | None:
    if _falsey(value):
        return f'{workflow} {scope}: telemetry is explicitly enabled'
    if not _truthy(value):
        return f'{workflow} {scope}: missing {ENV_NAME}=true'
    return None


def _local_workflow_target(job: object) -> str | None:
    if not isinstance(job, dict):
        return None
    target = job.get('uses')
    if not isinstance(target, str) or not target.startswith(LOCAL_WORKFLOW_PREFIX):
        return None
    return target[len(LOCAL_WORKFLOW_PREFIX) :].split('@', 1)[0]


def _check_workflow(
    workflow: Path,
    data: object,
    workflows: dict[str, tuple[Path, object]],
    violations: list[str],
    visited: set[str],
) -> None:
    key = workflow.name
    if key in visited:
        return
    visited.add(key)
    jobs = data.get('jobs') if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        if workflow.name in KNOWN_SERVICE_WORKFLOWS:
            violations.append(f'{workflow}: no jobs found')
        return

    workflow_env = data.get('env')
    known_jobs = KNOWN_SERVICE_JOBS.get(workflow.name, set())
    for name, job in jobs.items():
        target = _local_workflow_target(job)
        if target:
            callee = workflows.get(target)
            if callee is None:
                violations.append(f'{workflow} job {name}: local workflow {target} not found')
            else:
                _check_workflow(callee[0], callee[1], workflows, violations, visited)
            continue

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

        violation = _check_value(workflow, f'job {name}', _effective_value(workflow_env, job_env))
        if violation:
            violations.append(violation)


def check_workflows(workflows_root: Path) -> list[str]:
    """Return job-scoped violations, including local reusable workflow callees."""
    workflows: dict[str, tuple[Path, object]] = {}
    for workflow in sorted(workflows_root.glob('*.y*ml')):
        workflows[workflow.name] = (
            workflow,
            yaml.safe_load(workflow.read_text(encoding='utf-8')) or {},
        )
    violations: list[str] = []
    visited: set[str] = set()
    for workflow, data in workflows.values():
        _check_workflow(workflow, data, workflows, violations, visited)
    return violations


def check_actions(actions_root: Path) -> list[str]:
    """Return step-scoped violations for composite actions that start Core."""
    violations: list[str] = []
    for action in sorted(actions_root.glob('**/action.y*ml')):
        data = yaml.safe_load(action.read_text(encoding='utf-8')) or {}
        runs = data.get('runs') if isinstance(data, dict) else None
        steps = runs.get('steps') if isinstance(runs, dict) else None
        if not isinstance(steps, list):
            continue
        for index, step in enumerate(steps):
            if not isinstance(step, dict) or not _has_marker(step):
                continue
            violation = _check_value(action, f'step {index}', _env(step.get('env')).get(ENV_NAME))
            if violation:
                violations.append(violation)
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = check_workflows(root / '.github' / 'workflows')
    violations.extend(check_actions(root / '.github' / 'actions'))
    if violations:
        print('\n'.join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
