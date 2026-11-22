#!/usr/bin/env python3
"""Fail CI when a workflow can start Core without disabling product telemetry."""

from __future__ import annotations

import re
from pathlib import Path
import sys

TRUE = re.compile(r"SPACE__DISABLE_TELEMETRY\\s*:\\s*["']?true["']?|SPACE__DISABLE_TELEMETRY\\s*=\\s*true", re.IGNORECASE)
FALSE = re.compile(r"SPACE__DISABLE_TELEMETRY\\s*:\\s*["']?(?:false|0|no)["']?|SPACE__DISABLE_TELEMETRY\\s*=\\s*(?:false|0|no)", re.IGNORECASE)
SERVICE_MARKERS = ("regression_ci", "LANGBOT_DATA_ROOT", "SPACE__URL")
KNOWN_SERVICE_WORKFLOWS = {
    "artifact-accelerated-soak.yml",
    "artifact-qa.yml",
    "core-smoke.yml",
    "daily-endurance.yml",
    "persistence-acceptance.yml",
    "run-tests.yml",
}


def check_workflows(workflows_root: Path) -> list[str]:
    """Return violations for Core/service CI lanes under *workflows_root*."""
    violations: list[str] = []
    for workflow in sorted(workflows_root.glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        if workflow.name not in KNOWN_SERVICE_WORKFLOWS and not any(marker in text for marker in SERVICE_MARKERS):
            continue
        if FALSE.search(text):
            violations.append(f"{workflow}: SPACE__DISABLE_TELEMETRY is explicitly false")
        elif not TRUE.search(text):
            violations.append(f"{workflow}: missing SPACE__DISABLE_TELEMETRY=true")
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
