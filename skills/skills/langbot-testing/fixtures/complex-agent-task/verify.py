#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    baseline = Path(__file__).resolve().parent / "workspace"

    for relative in ("TASK.md", "tests/test_order_engine.py", "acceptance_check.py"):
        if (workspace / relative).read_bytes() != (baseline / relative).read_bytes():
            raise AssertionError(f"protected fixture changed: {relative}")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if tests.returncode != 0:
        raise AssertionError(f"unit tests failed:\n{tests.stdout}\n{tests.stderr}")

    acceptance = subprocess.run(
        [sys.executable, "acceptance_check.py"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if acceptance.returncode != 0 or "ACCEPTANCE_PASS" not in acceptance.stdout:
        raise AssertionError(f"acceptance failed:\n{acceptance.stdout}\n{acceptance.stderr}")

    result = json.loads((workspace / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["tests_run"] == 12
    assert result["acceptance"] == "PASS"
    report = (workspace / "AGENT_REPORT.md").read_text(encoding="utf-8")
    folded_report = report.casefold()
    assert "initial" in folded_report and "fail" in folded_report, "report missing initial failure section"
    assert "root causes" in folded_report, "report missing section: root causes"
    assert any(
        heading in folded_report
        for heading in (
            "changed files",
            "files changed",
            "files modified",
            "modified files",
            "changes made",
        )
    ), "report missing section: changed files"
    assert "verification" in folded_report, "report missing section: verification"
    assert report.rstrip().endswith("COMPLEX_AGENT_TASK_OK tests=12 acceptance=PASS")
    print("HOST_VERIFY_PASS tests=12 acceptance=PASS protected=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
