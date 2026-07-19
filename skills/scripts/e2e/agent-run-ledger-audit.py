#!/usr/bin/env python3
"""Audit one persisted AgentRunner run without exposing authorization secrets."""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import pathlib
import re
import sys
import urllib.parse

import sqlalchemy
import yaml
from sqlalchemy.ext.asyncio import create_async_engine


def database_url(repo: pathlib.Path) -> str:
    config = yaml.safe_load((repo / "data/config.yaml").read_text(encoding="utf-8")) or {}
    database = config.get("database", {})
    kind = database.get("use", "sqlite")
    if kind == "sqlite":
        path = pathlib.Path(database.get("sqlite", {}).get("path", "data/langbot.db"))
        if not path.is_absolute():
            path = repo / path
        return f"sqlite+aiosqlite:///{path}"
    if kind in {"postgres", "postgresql"}:
        values = database.get("postgresql", {})
        user = urllib.parse.quote_plus(str(values.get("user", "postgres")))
        password = urllib.parse.quote_plus(str(values.get("password", "postgres")))
        host = values.get("host", "127.0.0.1")
        port = values.get("port", 5432)
        name = values.get("database", "postgres")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
    raise RuntimeError(f"Unsupported database backend: {kind}")


def load_json(value: str | None, *, field: str, failures: list[dict]) -> object:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        failures.append({"kind": "invalid_json", "field": field, "reason": str(exc)})
        return {}


def parse_created_after(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed


def event_matches_tool_call(data_json: str | None, tool_name: str, parameters: dict | None) -> bool:
    try:
        data = json.loads(data_json or "{}")
    except (TypeError, ValueError):
        return False
    if not isinstance(data, dict) or data.get("tool_name") != tool_name:
        return False
    return parameters is None or data.get("parameters") == parameters


def collect_result_texts(value: object) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "text" and isinstance(item, str):
                texts.append(item)
            else:
                texts.extend(collect_result_texts(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(collect_result_texts(item))
    return texts


async def audit(
    repo: pathlib.Path,
    run_id: str | None,
    *,
    created_after: datetime.datetime | None = None,
    expected_tool_name: str | None = None,
    expected_parameters: dict | None = None,
    expected_result_text: str | None = None,
) -> dict:
    engine = create_async_engine(database_url(repo))
    failures: list[dict] = []
    warnings: list[dict] = []
    try:
        async with engine.connect() as connection:
            if run_id:
                run_row = (await connection.execute(
                    sqlalchemy.text("SELECT * FROM agent_run WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )).mappings().first()
            elif expected_tool_name:
                query = "SELECT * FROM agent_run"
                params = {}
                if created_after is not None:
                    query += " WHERE created_at >= :created_after"
                    params["created_after"] = created_after
                query += " ORDER BY id DESC LIMIT 100"
                candidates = (await connection.execute(sqlalchemy.text(query), params)).mappings().all()
                run_row = None
                for candidate in candidates:
                    started_rows = (await connection.execute(
                        sqlalchemy.text(
                            "SELECT data_json FROM agent_run_event "
                            "WHERE run_id = :run_id AND type = 'tool.call.started' ORDER BY sequence"
                        ),
                        {"run_id": str(candidate["run_id"])},
                    )).mappings().all()
                    if any(
                        event_matches_tool_call(row.get("data_json"), expected_tool_name, expected_parameters)
                        for row in started_rows
                    ):
                        run_row = candidate
                        break
            else:
                run_row = (await connection.execute(
                    sqlalchemy.text("SELECT * FROM agent_run ORDER BY id DESC LIMIT 1")
                )).mappings().first()
            if run_row is None:
                status = "fail" if expected_tool_name else "env_issue"
                return {
                    "status": status,
                    "reason": "No AgentRunner run contains the expected tool call." if expected_tool_name else "No matching AgentRunner run exists.",
                    "failures": [{"kind": "expected_tool_call_missing"}] if expected_tool_name else [],
                    "warnings": [],
                }

            selected_run_id = str(run_row["run_id"])
            event_rows = (await connection.execute(
                sqlalchemy.text("SELECT sequence, type, data_json, metadata_json FROM agent_run_event WHERE run_id = :run_id ORDER BY sequence"),
                {"run_id": selected_run_id},
            )).mappings().all()
    finally:
        await engine.dispose()

    authorization = load_json(run_row.get("authorization_json"), field="agent_run.authorization_json", failures=failures)
    tools = authorization.get("resources", {}).get("tools", []) if isinstance(authorization, dict) else []
    allowed_tools: dict[str, dict] = {}
    incomplete_tool_metadata: list[dict] = []
    for tool in tools if isinstance(tools, list) else []:
        if not isinstance(tool, dict):
            incomplete_tool_metadata.append({"tool_name": "", "missing": ["tool object"]})
            continue
        name = str(tool.get("tool_name", ""))
        missing = []
        if not name:
            missing.append("tool_name")
        if not str(tool.get("description", "")).strip():
            missing.append("description")
        if not isinstance(tool.get("parameters"), dict):
            missing.append("parameters")
        if not (tool.get("source") or tool.get("tool_type") or tool.get("source_id")):
            missing.append("owner")
        if missing:
            incomplete_tool_metadata.append({"tool_name": name, "missing": missing})
        if name:
            allowed_tools[name] = tool
    if incomplete_tool_metadata:
        failures.append({"kind": "incomplete_tool_metadata", "tools": incomplete_tool_metadata})

    starts: dict[str, list[dict]] = {}
    completions: dict[str, list[dict]] = {}
    event_types: list[str] = []
    invalid_event_json = 0
    suspicious_errors: list[dict] = []
    forbidden_pattern = re.compile(r"invalid json(?: arguments)?|unauthori[sz]ed|permission denied|forbidden|timed?\s*out|timeout", re.I)

    def error_surface(value: object) -> list[str]:
        """Collect diagnostic fields without treating normal tool parameters as errors."""
        collected: list[str] = []
        if not isinstance(value, dict):
            return collected
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {"error", "code", "status", "reason", "error_message"} and item is not None and item != "":
                collected.append(str(item))
            if isinstance(item, dict):
                collected.extend(error_surface(item))
        return collected

    for row in event_rows:
        event_type = str(row["type"])
        event_types.append(event_type)
        before = len(failures)
        data = load_json(row.get("data_json"), field=f"agent_run_event[{row['sequence']}].data_json", failures=failures)
        invalid_event_json += int(len(failures) > before)
        if not isinstance(data, dict):
            failures.append({"kind": "invalid_event_payload", "sequence": row["sequence"], "type": event_type})
            continue
        if event_type in {"tool.call.started", "tool.call.completed"}:
            call_id = str(data.get("tool_call_id", ""))
            item = {"sequence": row["sequence"], "tool_name": str(data.get("tool_name", "")), "data": data}
            if not call_id:
                failures.append({"kind": "missing_tool_call_id", "sequence": row["sequence"], "type": event_type})
            elif event_type == "tool.call.started":
                starts.setdefault(call_id, []).append(item)
            else:
                completions.setdefault(call_id, []).append(item)
        diagnostic_text = "\n".join(error_surface(data))
        if event_type == "run.failed":
            diagnostic_text += "\n" + json.dumps(data, ensure_ascii=True)
        match = forbidden_pattern.search(diagnostic_text)
        if match:
            suspicious_errors.append({"sequence": row["sequence"], "type": event_type, "signal": match.group(0)})

    if run_row["status"] != "completed":
        failures.append({"kind": "run_status", "actual": run_row["status"], "expected": "completed"})
    if "run.completed" not in event_types:
        failures.append({"kind": "missing_run_completed_event"})
    if "run.failed" in event_types:
        failures.append({"kind": "run_failed_event"})

    all_call_ids = sorted(set(starts) | set(completions))
    unauthorized_calls = []
    for call_id in all_call_ids:
        started = starts.get(call_id, [])
        completed = completions.get(call_id, [])
        if len(started) != 1 or len(completed) != 1:
            failures.append({"kind": "tool_call_pairing", "tool_call_id": call_id, "started": len(started), "completed": len(completed)})
            continue
        if started[0]["tool_name"] != completed[0]["tool_name"]:
            failures.append({"kind": "tool_name_mismatch", "tool_call_id": call_id})
        if started[0]["sequence"] >= completed[0]["sequence"]:
            failures.append({"kind": "tool_call_order", "tool_call_id": call_id})
        if started[0]["tool_name"] not in allowed_tools:
            unauthorized_calls.append({"tool_call_id": call_id, "tool_name": started[0]["tool_name"]})
    if unauthorized_calls:
        failures.append({"kind": "unauthorized_tool_calls", "calls": unauthorized_calls})
    if suspicious_errors:
        failures.append({"kind": "forbidden_error_signals", "events": suspicious_errors})
    if not event_rows:
        failures.append({"kind": "missing_run_events"})
    if not tools:
        warnings.append({"kind": "no_authorized_tools", "reason": "The run authorization snapshot exposes no tools."})

    expected_call_summary = None
    if expected_tool_name:
        matching_starts = [
            item
            for items in starts.values()
            for item in items
            if item["tool_name"] == expected_tool_name
            and (expected_parameters is None or item["data"].get("parameters") == expected_parameters)
        ]
        if len(matching_starts) != 1:
            failures.append({"kind": "expected_tool_call_count", "actual": len(matching_starts), "expected": 1})
        matching_completions = []
        for started in matching_starts:
            call_id = str(started["data"].get("tool_call_id", ""))
            matching_completions.extend(completions.get(call_id, []))
        result_text_match = expected_result_text is None or any(
            expected_result_text in collect_result_texts(completed["data"].get("result"))
            for completed in matching_completions
        )
        if expected_result_text is not None and not result_text_match:
            failures.append({"kind": "expected_tool_result_text_missing"})
        expected_call_summary = {
            "tool_name": expected_tool_name,
            "parameters_match_required": expected_parameters is not None,
            "matched_started_count": len(matching_starts),
            "matched_completed_count": len(matching_completions),
            "result_text_match_required": expected_result_text is not None,
            "result_text_match": result_text_match,
        }

    metrics = {
        "event_count": len(event_rows),
        "tool_call_started": sum(len(items) for items in starts.values()),
        "tool_call_completed": sum(len(items) for items in completions.values()),
        "tool_call_ids": len(all_call_ids),
        "authorized_tool_count": len(allowed_tools),
        "invalid_event_json": invalid_event_json,
        "suspicious_error_count": len(suspicious_errors),
    }
    return {
        "status": "pass" if not failures else "fail",
        "reason": "Agent run ledger audit passed." if not failures else f"Agent run ledger audit found {len(failures)} invariant failure(s).",
        "run": {
            "run_id": selected_run_id,
            "runner_id": run_row["runner_id"],
            "status": run_row["status"],
            "created_at": str(run_row["created_at"]),
            "finished_at": str(run_row["finished_at"]),
        },
        "metrics": metrics,
        "expected_tool_call": expected_call_summary,
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--created-after")
    parser.add_argument("--expected-tool-name")
    parser.add_argument("--expected-parameters-json")
    parser.add_argument("--expected-result-text")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        expected_parameters = None
        if args.expected_parameters_json:
            expected_parameters = json.loads(args.expected_parameters_json)
            if not isinstance(expected_parameters, dict):
                raise ValueError("--expected-parameters-json must decode to an object")
        if (expected_parameters is not None or args.expected_result_text) and not args.expected_tool_name:
            raise ValueError("--expected-tool-name is required with expected parameters or result text")
        report = asyncio.run(audit(
            pathlib.Path(args.repo).resolve(),
            args.run_id,
            created_after=parse_created_after(args.created_after),
            expected_tool_name=args.expected_tool_name,
            expected_parameters=expected_parameters,
            expected_result_text=args.expected_result_text,
        ))
    except Exception as exc:  # noqa: BLE001 - probe must classify environment failures
        report = {"status": "env_issue", "reason": str(exc), "failures": [], "warnings": []}
    pathlib.Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["status"] == "pass" else 2 if report["status"] == "env_issue" else 1


if __name__ == "__main__":
    sys.exit(main())
