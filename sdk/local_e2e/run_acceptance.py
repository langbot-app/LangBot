#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/rock/work/langbot-sdk-shared-local-e2e")
OUT = ROOT / "local_e2e" / "acceptance.json"


def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": cmd,
        "exit_code": p.returncode,
        "stdout": p.stdout[-4000:],
        "stderr": p.stderr[-4000:],
    }


results = {
    "candidate_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "registration_fanin": run(
        ["uv", "run", "python", "local_e2e/registration_fanin.py"]
    ),
    "shared_slots_subprocess": run(
        [
            "uv",
            "run",
            "pytest",
            "tests/runtime/plugin/test_shared_worker_subprocess.py",
            "-q",
        ]
    ),
    "installation_lifecycle": run(
        [
            "uv",
            "run",
            "pytest",
            "tests/runtime/plugin/test_installation_manager.py",
            "-q",
        ]
    ),
    "stdio_transport": run(
        [
            "uv",
            "run",
            "pytest",
            "tests/runtime/io/test_connections.py",
            "tests/runtime/io/test_controllers.py",
            "-q",
        ]
    ),
}
results["assertions"] = {
    "six_concurrent_large_registrations": results["registration_fanin"]["exit_code"]
    == 0
    and '"registered": 6' in results["registration_fanin"]["stdout"],
    "two_workspaces_one_pid_two_slots": results["shared_slots_subprocess"]["exit_code"]
    == 0,
    "config_and_file_isolation": results["shared_slots_subprocess"]["exit_code"] == 0,
    "sibling_detach_survives": results["shared_slots_subprocess"]["exit_code"] == 0,
    "dedicated_process_separate": results["shared_slots_subprocess"]["exit_code"] == 0,
    "lifecycle_failure_cancel_capacity_regressions": results["installation_lifecycle"][
        "exit_code"
    ]
    == 0,
    "one_shot_stdio_control_lane": results["stdio_transport"]["exit_code"] == 0,
}
results["passed"] = all(results["assertions"].values())
OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
print(
    json.dumps(
        {"passed": results["passed"], "assertions": results["assertions"]},
        ensure_ascii=False,
    )
)
raise SystemExit(0 if results["passed"] else 1)
