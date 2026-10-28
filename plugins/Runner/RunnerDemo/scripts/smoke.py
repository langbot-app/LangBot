"""Install and exercise both components against an authorized LangBot instance.

Requires httpx. Authentication stays in memory and is never written to receipts.
Run: LANGBOT_TOKEN=... python scripts/smoke.py --base-url http://localhost:5399
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "langbot-team/RunnerDemo"


def checked(response):
    if response.is_error:
        raise RuntimeError(f"{response.status_code} {response.request.url.path}: {response.text}")
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(str(body))
    return body.get("data", {})


def install_and_test(client: httpx.Client, package: Path, receipt: Path) -> dict:
    with package.open("rb") as file:
        task_id = checked(
            client.post(
                "/api/v1/plugins/install/local",
                files={"file": (package.name, file, "application/zip")},
            )
        )["task_id"]
    for _ in range(120):
        task = checked(client.get(f"/api/v1/system/tasks/{task_id}"))
        if task["runtime"]["done"]:
            if task["runtime"].get("exception"):
                raise RuntimeError(str(task["runtime"]["exception"]))
            break
        time.sleep(1)
    else:
        raise TimeoutError("Plugin installation did not finish within 120 seconds")
    print("Installed:", PLUGIN, flush=True)
    for _ in range(30):
        descriptors = checked(client.get("/api/v1/agents/_/metadata")).get("event_processors", [])
        found = {d["id"].rsplit("/", 1)[-1]: d for d in descriptors if d["id"].startswith("plugin:" + PLUGIN + "/")}
        if set(found) == {"community", "observer"}:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Both Runner components must be registered")

    ids, configs = {}, {}
    existing = checked(client.get("/api/v1/agents")).get("agents", [])
    for component, title in [
        ("community", "示例工坊 · 社区助手"),
        ("observer", "示例工坊 · 事件观察员"),
    ]:
        descriptor = found[component]
        parameters = {item["name"]: item.get("default") for item in descriptor["config_schema"]}
        parameters.update(
            {"allow_demo_failure": True, "announce_departures": True}
            if component == "community"
            else {"include_payload": True}
        )
        configs[component] = parameters
        prior = next(
            (a for a in existing if a.get("name") == title and a.get("component_ref") == descriptor["id"]),
            None,
        )
        if prior:
            processor_id = prior["uuid"]
        else:
            processor_id = checked(
                client.post(
                    "/api/v1/agents",
                    json={
                        "kind": "event_processor",
                        "name": title,
                        "emoji": "🧩",
                        "description": "RunnerDemo: deterministic examples, no model needed.",
                    },
                )
            )["uuid"]
        checked(
            client.put(
                f"/api/v1/agents/{processor_id}",
                json={"component_ref": descriptor["id"], "parameters": parameters},
            )
        )
        ids[component] = processor_id
        print("Configured:", component, processor_id, flush=True)
    report = {"plugin": PLUGIN, "processors": ids, "cases": []}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        for scenario in json.loads((ROOT / "examples/scenarios.json").read_text()):
            processor_id = ids[scenario["component"]]
            payload = json.loads((ROOT / "examples" / scenario["file"]).read_text())
            response = client.post(f"/api/v1/agents/{processor_id}/debug/stream", json=payload, timeout=45)
            response.raise_for_status()
            frames = [json.loads(line) for line in response.text.splitlines() if line.strip()]
            errors = [f for f in frames if f.get("kind") == "error" or f.get("data", {}).get("type") == "run.failed"]
            if bool(errors) != scenario["expect_error"]:
                raise AssertionError(f"Unexpected outcome for {scenario['file']}: {frames}")
            results = [f["data"] for f in frames if f.get("kind") == "result"]
            run_ids = {r.get("run_id") for r in results if r.get("run_id")}
            if len(run_ids) != 1:
                raise AssertionError(f"Expected exactly one invocation: {run_ids}")
            run_id = next(iter(run_ids))
            detail = checked(client.get(f"/api/v1/agents/{processor_id}/runs/{run_id}/events"))
            run = detail["run"]
            expected_status = "failed" if scenario["expect_error"] else "completed"
            if run["status"] != expected_status or not detail["items"]:
                raise AssertionError(f"Persisted run outcome mismatch: {run}")
            actions = [r["data"] for r in results if r.get("type") == "tool.call.completed"]
            replies = [a for a in actions if a.get("tool_name") == "event_reply"]
            for action in replies:
                if not action.get("result", {}).get("mock"):
                    raise AssertionError("Debug reply must be explicitly marked Mock")
            if len(actions) != scenario["expected_actions"] or len(replies) != scenario["expected_replies"]:
                raise AssertionError(f"Action count mismatch for {scenario['file']}: {actions}")
            if scenario["component"] == "observer" and actions:
                raise AssertionError("Observer must not call tools")
            case = {
                "file": scenario["file"],
                "run_id": run["run_id"],
                "status": run["status"],
                "events": len(detail["items"]),
                "actions": len(actions),
                "mock_replies": len(replies),
                "expected_error": scenario["expect_error"],
            }
            report["cases"].append(case)
            receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(case, ensure_ascii=False), flush=True)
    finally:
        # Keep intentional failure opt-in, even after a test failure.
        configs["community"]["allow_demo_failure"] = False
        checked(
            client.put(
                f"/api/v1/agents/{ids['community']}",
                json={"parameters": configs["community"]},
            )
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--package",
        type=Path,
        default=ROOT / "dist/langbot-team-RunnerDemo-0.2.1.lbpkg",
    )
    parser.add_argument("--receipt", type=Path, default=ROOT / "data/smoke-results.json")
    args = parser.parse_args()
    token = os.environ.get("LANGBOT_TOKEN")
    api_key = os.environ.get("LANGBOT_API_KEY")
    if not token and not api_key:
        parser.error("Set LANGBOT_TOKEN or LANGBOT_API_KEY with resource manage and operate permissions")
    headers = {"Authorization": "Bearer " + token} if token else {"X-API-Key": api_key}
    if os.environ.get("LANGBOT_WORKSPACE_ID"):
        headers["X-Workspace-Id"] = os.environ["LANGBOT_WORKSPACE_ID"]
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=30) as client:
        install_and_test(client, args.package, args.receipt)


if __name__ == "__main__":
    main()
