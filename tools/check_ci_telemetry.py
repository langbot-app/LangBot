#!/usr/bin/env python3
"""Fail CI when a service job can start Core without disabling product telemetry."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

SERVICE_MARKERS = ("regression_ci", "LANGBOT_DATA_ROOT", "SPACE__URL")
KNOWN_SERVICE_WORKFLOWS = {
    "artifact-accelerated-soak.yml",
    "artifact-qa.yml",
    "core-smoke.yml",
    "daily-endurance.yml",
    "persistence-acceptance.yml",
    "run-tests.yml",
}


def _text(value: object) -> str:
    return yaml.safe_dump(value, sort_keys=True)


def _disabled(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _enabled(value: object) -> bool:
    return str(value).strip().lower() in {"false", "0", "no"}


def _service_job(job: object) -> bool:
    return any(marker in _text(job) for marker in SERVICE_MARKERS)


def check_workflows(workflows_root: Path) -> list[str]:
    """Return job-scoped violations for Core/service CI lanes."""
    violations: list[str] = []
    for workflow in sorted(workflows_root.glob("*.y*ml")):
        data = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, dict):
            continue
        workflow_env = data.get("env") if isinstance(data.get("env"), dict) else {}
        if _enabled(workflow_env.get("SPACE__DISABLE_TELEMETRY")):
            violations.append(f"{workflow}: workflow env explicitly enables telemetry")
        for name, job in jobs.items():
            if not _service_job(job):
                continue
            job_env = job.get("env") if isinstance(job, dict) and isinstance(job.get("env"), dict) else {}
            value = job_env.get("SPACE__DISABLE_TELEMETRY", workflow_env.get("SPACE__DISABLE_TELEMETRY"))
            if _enabled(value):
                violations.append(f"{workflow} job {name}: telemetry is explicitly enabled")
            elif not _disabled(value):
                violations.append(f"{workflow} job {name}: missing SPACE__DISABLE_TELEMETRY=true")
        if workflow.name in KNOWN_SERVICE_WORKFLOWS and not jobs:
            violations.append(f"{workflow}: no jobs found")
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    violations = check_workflows(root)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
