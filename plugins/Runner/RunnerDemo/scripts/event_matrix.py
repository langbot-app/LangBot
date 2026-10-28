"""Check every standard EBA event against an installed Event Observer instance.

Use a dedicated test instance with include_payload enabled. The observer must
not have Bot bindings; all requests use the local debugger and make no replies.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def check_matrix(client: httpx.Client, processor_id: str, receipt: Path) -> dict:
    cases = json.loads((ROOT / "examples/event-matrix.json").read_text())
    report = {"processor_id": processor_id, "cases": []}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        response = client.post(
            f"/api/v1/agents/{processor_id}/debug/stream",
            json=case["request"],
            timeout=30,
        )
        frames = []
        if response.is_success:
            frames = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        errors = [frame for frame in frames if frame.get("kind") == "error"]
        results = [frame["data"] for frame in frames if frame.get("kind") == "result"]
        failed = (
            response.status_code >= 400 or bool(errors) or any(item.get("type") == "run.failed" for item in results)
        )
        assert failed == case["expected_error"], (
            case["name"],
            response.status_code,
            frames,
        )
        assert response.status_code < 500, (case["name"], response.status_code)
        run_ids = {item["run_id"] for item in results if item.get("run_id")}
        assert len(run_ids) <= 1, (case["name"], run_ids)
        assert not any(item.get("type", "").startswith("tool.call.") for item in results), case["name"]
        if not failed:
            assert len(run_ids) == 1, case["name"]
            assert sum(item.get("type") == "run.completed" for item in results) == 1, case["name"]
            logs = [item["data"]["text"] for item in results if item.get("type") == "processor.log"]
            payloads = []
            for line in logs:
                try:
                    parsed = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, dict) and "timestamp" in parsed:
                    payloads.append(parsed)
            assert len(payloads) == 1, (
                case["name"],
                "Enable include_payload on the observer",
            )
            observed = payloads[0]
            assert observed["type"] == case["request"]["event_type"]
            for key, value in case["request"]["data"].items():
                if key in {"message_chain", "new_content"}:
                    for original, restored in zip(value, observed[key], strict=True):
                        assert all(restored.get(k) == v for k, v in original.items()), case["name"]
                elif not isinstance(value, dict):
                    assert observed[key] == value, (case["name"], key)
                else:
                    assert all(observed[key].get(k) == v for k, v in value.items()), (
                        case["name"],
                        key,
                    )
        if run_ids:
            run_id = next(iter(run_ids))
            detail_response = client.get(f"/api/v1/agents/{processor_id}/runs/{run_id}/events")
            detail_response.raise_for_status()
            detail = detail_response.json()["data"]
            assert detail["run"]["status"] == ("failed" if failed else "completed"), case["name"]
        else:
            run_id = None
        row = {
            "name": case["name"],
            "event_type": case["request"]["event_type"],
            "run_id": run_id,
            "expected_error": failed,
            "http_status": response.status_code,
            "passed": True,
        }
        report["cases"].append(row)
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--processor-id", required=True)
    parser.add_argument("--receipt", type=Path, default=ROOT / "data/event-matrix-results.json")
    args = parser.parse_args()
    token, key = os.environ.get("LANGBOT_TOKEN"), os.environ.get("LANGBOT_API_KEY")
    if not token and not key:
        parser.error("Set LANGBOT_TOKEN or LANGBOT_API_KEY")
    headers = {"Authorization": "Bearer " + token} if token else {"X-API-Key": key}
    if os.environ.get("LANGBOT_WORKSPACE_ID"):
        headers["X-Workspace-Id"] = os.environ["LANGBOT_WORKSPACE_ID"]
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=30) as client:
        check_matrix(client, args.processor_id, args.receipt)


if __name__ == "__main__":
    main()
