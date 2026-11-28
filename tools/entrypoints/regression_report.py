"""Summarize a completed Core regression run from its saved evidence."""

import argparse
import json
import math
from pathlib import Path
import sys


def read_json(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        raise ValueError(f'{path}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected an object')
    return data


def daily_workload(root, profile, gate):
    recorded = None
    if profile.get('coverage_suite') == 'endurance' or 'mixed' in gate:
        recorded = 'mixed'
    elif profile.get('coverage_suite') == 'scenarios':
        recorded = 'legacy' if 'execution' in profile else 'contracts'

    marker = root.parent / 'daily-workload.txt'
    if marker.exists():
        workload = marker.read_text().strip()
        if workload not in ('mixed', 'contracts', 'legacy'):
            raise ValueError(f'{marker}: unknown workload {workload!r}')
        if recorded and workload != recorded:
            raise ValueError(f'{marker}: workload {workload!r} conflicts with recorded {recorded!r} run')
        return workload
    return recorded or 'legacy'


def daily_details(workload, budget, gate, suite, profile, mixed, coverage):
    print(f'Workload: `{workload}`. Configured execution guard: {budget:g} seconds.')
    if workload == 'mixed':
        print(
            'Configured for one Workspace, three HTTP Bots and separate mock generation endpoints. '
            'The mixed verdict requires Box hostname isolation and measured tool-event overlap.\n'
        )
    elif workload == 'contracts':
        print('One finite contract pass with the selected local groups and owned-service restart checks.\n')
    else:
        print('Legacy scenarios use an 1800-second execution budget with 120 seconds for drain and 60 for cooldown.\n')
    if workload == 'mixed':
        print(f'Configured mixed-load phases: `{profile.get("phases", "not reported")}`.')
        print(
            f'Mixed evidence: {mixed.get("outcome", "missing")}; counts: `{mixed.get("counts", {})}`; '
            f'Provider requests: `{mixed.get("provider_requests", {})}`; '
            f'Box tool-event overlap: `{mixed.get("box_tool_event_overlap", "not reported")}`.\n'
        )
        for phase in suite.get('phases', []):
            print(
                f'Phase `{phase.get("name")}`: ledger closeout `{phase.get("ledger_closeout", {}).get("matched", "not reported")}`; '
                f'HTTP concurrency `{phase.get("http_concurrency", {})}`; '
                f'resource/queue observations `{phase.get("resource_observations", {})}`.\n'
            )
    else:
        print(
            f'Required first pass complete: {suite.get("first_pass_complete", "not reported")}; '
            f'cycles: {len(suite.get("cycles", []))}; requests: {suite.get("requests", "not reported")}.'
        )
        print(f'Final ledger reconciliation: {suite.get("ledger_closeout", {}).get("matched", "not reported")}.\n')
        data = suite.get('test_data', {})
        print(
            f'Observed conversations: {data.get("observed_conversations", "not reported")}; '
            f'AgentRuns: {data.get("observed_agent_runs", "not reported")}; '
            f'group sessions: {data.get("group_sessions", "not reported")}; '
            f'owned API resources: {data.get("owned_api_resources", "not reported")}.\n'
        )
    print(f'Enabled local groups: {gate.get("scenario_groups", "not reported")}.\n')
    restart = gate.get('restart_checks')
    if restart:
        print(
            f'Owned-service restart checks: {restart.get("outcome", "not reported")}; '
            f'{restart.get("elapsed_seconds", 0):.2f}s, deducted from the shared budget.\n'
        )
        for error in restart.get('errors', []):
            print(f'Restart check error: {error}')
    observations = suite.get('observations', {})
    if 'successful_requests_per_second' in observations:
        print(f'Successful throughput: {observations["successful_requests_per_second"]:.3f} RPS.\n')
    if observations.get('step_p95_seconds'):
        print('| Case | Full-step P95 (s) |\n|---|---:|')
        for name, p95 in observations['step_p95_seconds'].items():
            print(f'| {name} | {p95} |')
    for kind, values in coverage.get('kinds', {}).items():
        print(f'\n{kind} behavior evidence: {values["decided"]} / {values["total"]}; statuses: {values["status"]}.')
    if suite.get('resources', {}).get('targets'):
        print('\n| Resource | Metric | Retained growth | Allowance |\n|---|---|---:|---:|')
        for target, metrics in suite['resources']['targets'].items():
            for metric, values in metrics.items():
                print(
                    f'| {target} | {metric} | {values.get("growth", "unavailable")} | {values.get("allowance", "unavailable")} |'
                )


def summarize(mode, root, sha=None, step_outcome=None):
    gate = read_json(root / 'gate/gate.json')
    suite = read_json(root / 'gate/suite/summary.json')
    coverage = read_json(root / 'gate/suite/coverage.json')
    profile = read_json(root / 'gate/suite/profile.json')
    manifest = read_json(root / 'plugins/manifest.json')
    errors = list(gate.get('resource_errors', [])) + list(gate.get('coverage_errors', []))
    if gate.get('infrastructure_error'):
        errors.append(f'Preparation or teardown failed: {gate["infrastructure_error"]}')
    if not gate or not suite:
        errors.append('Missing verdict; inspect preparation and service logs.')
    recorded_suite = profile.get('coverage_suite')
    if 'api_fixed_only' in gate or 'api_seed' in gate:
        recorded_suite = 'api'
    elif 'mixed' in gate:
        recorded_suite = 'endurance'
    if mode == 'daily':
        allowed_suites = ('scenarios', 'endurance')
        label = 'Daily regression'
        workload = daily_workload(root, profile, gate)
        budget = {'mixed': 900, 'contracts': 300, 'legacy': 1860}[workload]
        if recorded_suite == 'endurance':
            budget = gate.get('budget_seconds', budget)
        mixed = read_json(root / 'gate/mixed.json')
        if workload == 'mixed' and mixed.get('passed') is not True:
            errors.append('Missing or unsuccessful independent mixed workload verdict.')
        errors.extend(mixed.get('errors', []))
    elif mode == 'core-smoke':
        allowed_suites = ('scenarios', 'smoke')
        label, budget = 'Core smoke', 300
    else:
        allowed_suites = ('api',)
        fixed = mode == 'api-fixed'
        label, budget = 'PR API contracts' if fixed else 'Daily API contracts', 600
        actual = gate.get('api_fixed_only')
        profile_mode = profile.get('vars', {}).get('api_fixed_only')
        if profile_mode is not None and actual is not profile_mode:
            errors.append('API profile and gate disagree about the run mode.')
        if (
            'api_fixed_only' not in gate
            and 'api_fixed_only' not in profile.get('vars', {})
            and gate.get('api_seed') is not None
        ):
            # Older Daily gates recorded the shuffled order before they recorded the mode.
            if any(name.startswith('shuffled_api_') for name in gate.get('case_order', [])):
                actual = False
        if gate.get('passed') is True and actual is not fixed:
            errors.append('API verdict does not match the requested run mode.')
        for contract in coverage.get('contracts', []):
            if contract.get('area') == 'api' and contract.get('status') in ('failed', 'incomplete', 'skipped'):
                errors.append(f'API contract `{contract["id"]}`: {contract["status"]}.')
    # Older artifacts can lack a suite identifier. Their recorded guard still distinguishes
    # a short Core Smoke from a legacy Daily run (which can spend part of its budget on restarts).
    if not recorded_suite and mode in ('core-smoke', 'daily') and 'budget_seconds' in gate:
        recorded_budget = gate['budget_seconds'] + gate.get('restart_elapsed_seconds', 0)
        if not math.isclose(recorded_budget, budget):
            errors.append(f'Recorded execution budget {recorded_budget:g}s does not match report mode {mode!r}.')
    if recorded_suite and recorded_suite not in allowed_suites:
        errors.append(f'Recorded suite `{recorded_suite}` does not match report mode `{mode}`.')
    if gate.get('timed_out'):
        errors.append(f'Suite exceeded its {budget:g}-second outer process guard.')
    outer_failed = bool(errors)
    errors.extend(suite.get('errors', []))
    if step_outcome and step_outcome != 'success':
        runner = 'API runner' if mode.startswith('api-') else 'Runner'
        errors.append(f'{runner} step: {step_outcome}.')

    passed = gate.get('passed') is True and suite.get('passed') is True and not errors
    outcome = 'PASS' if passed else 'FAIL / incomplete'
    if not passed and suite.get('outcome') == 'INCOMPLETE' and not outer_failed and mode == 'daily':
        outcome = 'INCOMPLETE'
    print(f'{label}: {outcome}\n')
    if sha:
        print(f'Core: `{sha}`.\n')
    if mode == 'daily':
        daily_details(workload, budget, gate, suite, profile, mixed, coverage)
        print(f'Plugin selection: `{manifest.get("selection", "not reported")}`.\n')
    elif mode == 'core-smoke':
        print(
            f'Suite execution: {gate.get("elapsed_seconds", "not reported")}/{budget} seconds; '
            f'{gate.get("requests", "not reported")} requests. Service preparation precedes the execution budget.\n'
        )
    else:
        print('Fixed order once.\n' if fixed else 'Fixed order followed by a seeded chain shuffle.\n')
        if not fixed:
            print(f'Shuffle seed: `{gate.get("api_seed", "not reported")}`.\n')
        print(
            f'Cases: {suite.get("requests", "not reported")}; statuses: {suite.get("status", "not reported")}; '
            f'suite execution: {suite.get("elapsed_seconds", "not reported")}s.\n'
        )
        print(f'API behavior contracts: {coverage.get("areas", {}).get("api", "not reported")}.\n')
        if coverage.get('http_observations'):
            print(
                f'Observed HTTP route templates (including preparation): {len(coverage["http_observations"]["routes"])}.\n'
            )
    for plugin in manifest.get('plugins', []):
        print(
            f'Plugin: `{plugin["id"]}@{plugin["version"]}`; installation readback: '
            f'`{plugin.get("installed", "not confirmed")}`.\n'
        )
    for error in errors:
        print(f'- {error}')
    return passed


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, epilog='Prints Markdown to stdout. Failed or incomplete runs exit with status 1.'
    )
    parser.add_argument('mode', choices=('api-fixed', 'api-daily', 'daily', 'core-smoke'), help='Expected kind of run')
    parser.add_argument('run_dir', type=Path, help='Run directory containing gate/ and plugins/')
    parser.add_argument('--sha', help='Core revision to show in the heading')
    parser.add_argument(
        '--step-outcome',
        choices=('success', 'failure', 'cancelled', 'skipped'),
        help='CI runner step outcome, when available',
    )
    args = parser.parse_args()
    try:
        passed = summarize(args.mode, args.run_dir, args.sha, args.step_outcome)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Regression report: FAIL / incomplete\n\n- Could not read run evidence: {exc}')
        passed = False
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
