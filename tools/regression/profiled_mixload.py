"""Compile and independently verify opt-in, restartable mixload profiles."""

from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import sqlite3

from tools.entrypoints.mock_llm import group_ack, group_markers, select_message
from tools.regression.run_ledger import connect_readonly, run_event_rows
from tools.regression.mixload_pacing import planned_group_slots
from tools.regression.mixload_profile import compile_mixload, load_mixload
from tools.regression.regression_mixed import BOX_HOST, RECOVERY_QUEUES, MissingEvidence, records, require

# Scenario -> (wire namespace, model, expected number of tool stages).
WIRE = {
    'chat': ('chat', 'mock-chat', 0),
    'box': ('box', 'mock-smoke-box', 2),
    'rag_chat': ('rag_chat', 'mock-rag', 0),
    'media_chat': ('chat', 'mock-media', 1),
    'memory_chat': ('chat', 'mock-memory', 2),
}
RESOURCE = re.compile(r'\$\{([^}]+)\}')


def reachable_resources(resources, cases):
    """Only prepare test resources required by at least one enabled scenario."""
    ids = {item['id'] for item in resources}
    used = set(RESOURCE.findall(json.dumps(cases))) & ids
    while True:
        needed = used | (set(RESOURCE.findall(json.dumps([r for r in resources if r['id'] in used]))) & ids)
        if needed == used:
            return [item for item in resources if item['id'] in needed]
        used = needed


def prepare_profile(base, path, *, box_backend='docker'):
    """Translate the small knobs-only user profile into the stock suite schema."""
    from tools.regression.mixload_cases import extend_mixload_profile

    profile = deepcopy(base)
    configured = load_mixload(path)
    result = extend_mixload_profile(
        profile, box_backend=box_backend, enable_memory='memory_chat' in (configured.include or ())
    )
    if result is not None:
        profile = result
    compiled = compile_mixload(profile['cases'], configured, default_phases=profile['phases'])
    used = {case['name'] for phase in compiled for case in phase.cases}
    if not used <= WIRE.keys():
        raise ValueError(f'Scenarios lack a wire oracle: {sorted(used - WIRE.keys())}')
    profile['cases'] = [case for case in profile['cases'] if case['name'] in used]
    profile['resources'] = reachable_resources(profile['resources'], profile['cases'])
    profile['phases'] = []
    for item in compiled:
        phase = {**item.phase}
        selected = [[row['name'], row['weight']] for row in item.cases]
        groups = phase.get('groups', 0)
        weights = sum(weight for _, weight in selected)
        if not groups or groups % weights:
            raise ValueError(f'{phase["name"]}: groups must be a positive multiple of total weight ({weights})')
        total = planned_group_slots(phase['duration_seconds'], phase['rps'], phase.get('max_requests'))
        if total < 2 * groups:
            raise ValueError(f'{phase["name"]}: needs at least two offered turns per group')
        phase['scenario_weights'] = selected
        if item.min_delivery_ratio is not None:
            phase['min_delivery_ratio'] = item.min_delivery_ratio
        profile['phases'].append(phase)
    limits = profile.get('resource_limits')
    if limits:
        if box_backend == 'host':
            limits.pop('containers', None)
        # A quick local profile uses a smaller but explicitly recorded observation window.
        shortest_load = min(phase['duration_seconds'] for phase in profile['phases'])
        shortest_cooldown = min(phase.get('cooldown_seconds', 0) for phase in profile['phases'])
        # The traffic sampler ticks every three seconds. Fit the windows to
        # short profiles without lowering the stock minimum number of samples.
        minimum_window = 3 * (limits['min_samples'] + 1)
        window = min(limits['window_seconds'], int(shortest_cooldown), int(shortest_load))
        if window < minimum_window:
            raise ValueError(f'Mixload resource evidence requires at least {minimum_window}s load and cooldown')
        limits['window_seconds'] = window
        limits['warmup_seconds'] = min(limits['warmup_seconds'], max(0, int(shortest_load) - window))
    for name in set(profile.get('thresholds', {}).get('max_p95_seconds', {})) - used:
        del profile['thresholds']['max_p95_seconds'][name]
    return profile


def box_evidence(db, run_id, case):
    """Require persisted successful execs and an identity from the selected backend."""
    check = case['box_exec']
    hits = []
    rows = run_event_rows(db, run_id, 'tool.call.completed')
    for _, data in rows:
        event = json.loads(data or '{}')
        if event.get('tool_name') != 'exec':
            continue
        result = event.get('result') or {}
        require(
            result.get('backend') == check['backend'] and result.get('exit_code') == 0,
            'Wrong Box execution backend/outcome',
        )
        if check['backend'] == 'docker':
            hostname = BOX_HOST.findall(result.get('stdout') or '')
            require(len(hostname) == 1, 'Docker execution lacks exactly one real sandbox hostname')
            identity = hostname[0]
        else:
            identity = result.get('session_id')
        require(isinstance(identity, str) and bool(identity), 'Box execution lacks a session identity')
        hits.append(identity)
    if len(hits) != check['count']:
        raise MissingEvidence(f'Expected {check["count"]} completed Box execs for {run_id}, found {len(hits)}')
    require(len(set(hits)) == 1, 'Box session changed within a request')
    return hits[0]


def check_phase_geometry(summary, rows, phase):
    """Cross-check stop, schedule accounting, observation and ledger evidence."""
    name = phase['name']
    expected = dict(phase['scenario_weights'])
    planned = planned_group_slots(phase['duration_seconds'], phase['rps'], phase.get('max_requests'))
    actual = Counter(row['case'] for row in rows)
    if not summary.get('verification_enabled') or 'slot_accounting' not in summary:
        raise MissingEvidence(f'{name}: configured phase lacks pacing or ledger evidence')
    require(set(actual) == set(expected), f'{name}: a selected scenario never ran or unexpected scenario ran')
    require(
        summary['health_samples'] > 0 and summary['health_failures'] == 0,
        f'{name}: health observations missing or failed',
    )
    require(summary['ledger_closeout']['matched'], f'{name}: ledger closeout does not match requests')
    require(
        summary['requests'] == summary['successful_requests'] == summary['verified_runs'] == len(rows),
        f'{name}: response/ledger counts differ',
    )
    require(summary['groups']['configured'] == phase['groups'], f'{name}: effective group count differs')
    require(not summary['group_failures'], f'{name}: groups did not complete two turns')
    sessions = summary['groups']['sessions']
    require(
        len(sessions) == phase['groups'] and set(sessions) == {row['group_id'] for row in rows},
        f'{name}: actual session set differs',
    )
    by_group = defaultdict(list)
    for row in rows:
        by_group[row['group_id']].append(row)
    assigned = Counter()
    seen_slots, seen_groups = set(), set()
    sequence = [case for case, weight in phase['scenario_weights'] for _ in range(weight)]
    members = phase.get('members_per_group', 3)
    for group, group_rows in by_group.items():
        session = sessions[group]
        require(len(group_rows) >= 2, f'{name}/{group}: fewer than two raw turns')
        require(
            len(group_rows) == session['requests_this_phase'] == session['successful_turns_total']
            and not session['failed'],
            f'{name}/{group}: summary and raw turn counts differ',
        )
        ordered = sorted(group_rows, key=lambda row: row['turn'])
        case = session['case']
        index = session['group_index']
        require(
            type(index) is int and 0 <= index < phase['groups'] and index not in seen_groups,
            f'{name}/{group}: invalid or duplicate group index',
        )
        seen_groups.add(index)
        require(case == sequence[index % len(sequence)], f'{name}/{group}: wrong configured group case')
        last_slot = -1
        require(
            case in expected and all(row['case'] == case for row in ordered),
            f'{name}/{group}: group changed its scenario',
        )
        for turn, row in enumerate(ordered, 1):
            slot = row['offered_slot']
            require(
                type(slot) is int
                and last_slot < slot < planned
                and slot not in seen_slots
                and slot % phase['groups'] == index,
                f'{name}/{group}: invalid, repeated or wrong offered slot',
            )
            when = slot / phase['rps']
            require(
                math.isclose(row['planned_elapsed_seconds'], when, rel_tol=0, abs_tol=1e-9)
                and row['elapsed'] + 1e-8 >= when,
                f'{name}/{group}: request timing differs from offered slot',
            )
            seen_slots.add(slot)
            last_slot = slot
            require(
                row['turn'] == turn and row['member_id'] == f'qa-member-{(turn - 1) % members:03d}',
                f'{name}/{group}: turn/member sequence differs',
            )
        require(
            set(session['members_this_phase']) == {row['member_id'] for row in ordered},
            f'{name}/{group}: summary and raw member sets differ',
        )
        assigned[case] += 1
    cycle = sum(expected.values())
    require(
        assigned == Counter({case: phase['groups'] // cycle * weight for case, weight in expected.items()}),
        f'{name}: group assignments do not match weights',
    )
    accounting = summary['slot_accounting']
    require(set(accounting) == set(expected), f'{name}: offered accounting scenario set differs')
    for case, item in accounting.items():
        quotient, remainder = divmod(planned, len(sequence))
        expected_offered = quotient * expected[case] + sequence[:remainder].count(case)
        require(
            item['offered'] == expected_offered == item['admitted'] + item['not_admitted']
            and item['admitted'] == actual[case],
            f'{name}/{case}: offered != admitted + not-admitted, or counters differ from actual requests',
        )
    delivery = len(rows) / planned
    floor = phase.get('min_delivery_ratio', 0)
    queues = summary['resource_observations']['queues']
    for key in RECOVERY_QUEUES:
        row = queues.get(key, {})
        if row.get('status') != 'observed' or 'cooldown_tail_max' not in row:
            raise MissingEvidence(f'{name}: no measured cooldown tail for {key}')
        require(row['cooldown_tail_max'] == 0, f'{name}: queue did not drain: {key}')
    return {
        'cases': dict(actual),
        'offered': planned,
        'admitted': len(rows),
        'not_admitted': planned - len(rows),
        'delivery_ratio': delivery,
        'min_delivery_ratio': floor,
        'delivery_floor_passed': delivery >= floor,
    }


def memory_events(db, run_id, turn):
    rows = run_event_rows(db, run_id, 'tool.call.completed')
    actual = [json.loads(data).get('tool_name') for _, data in rows]
    expected = ['remember', 'recall_memory'] if turn == 1 else ['recall_memory']
    require(actual == expected, 'Persisted memory tool sequence differs from the transaction')
    return len(actual)


def final_stage(case, turn):
    if case == 'memory_chat' and turn > 1:
        return 1
    return WIRE[case][2]


def verify_profiled_run(output_suite_dir, ledger_db, provider_records, profile):
    """Require all selected business scenarios and fail closed on missing evidence."""
    from tools.regression.mixload_cases import memory_scenario

    root = Path(output_suite_dir)
    result = {
        'passed': False,
        'outcome': 'INCOMPLETE',
        'business_evidence_passed': False,
        'delivery_floor_passed': None,
        'errors': [],
        'phases': {},
        'wire_stages': {},
    }
    try:
        catalogue = {case['name']: case for case in profile['cases']}
        expected_phases = {p['name'] for p in profile['phases']}
        observed_phases = {path.parent.name for path in root.glob('*/requests.jsonl')}
        if expected_phases - observed_phases:
            raise MissingEvidence(f'Missing measured phases: {sorted(expected_phases - observed_phases)}')
        require(expected_phases == observed_phases, 'Unexpected measured phase(s)')
        tokens, runs, box_sessions = {}, set(), defaultdict(set)
        bots_by_case = defaultdict(set)
        memory_turns = Counter()
        with closing(connect_readonly(ledger_db)) as db:
            db.execute('PRAGMA query_only=ON')
            for phase in profile['phases']:
                path = root / phase['name']
                rows = records(path / 'requests.jsonl')
                summary = json.loads((path / 'summary.json').read_text())
                result['phases'][phase['name']] = check_phase_geometry(summary, rows, phase)
                for row in rows:
                    token, group, case = row['token'], row['group_id'], row['case']
                    run_id = row.get('run', {}).get('run_id')
                    require(bool(token and group and run_id), 'Request has no token/group/persisted run')
                    require(
                        row['status'] == 'ok' and token not in tokens and run_id not in runs,
                        'Failed or duplicated request',
                    )
                    tokens[token] = row
                    runs.add(run_id)
                    stored = db.execute(
                        'SELECT status, conversation_id, bot_id FROM agent_run WHERE run_id=?', (run_id,)
                    ).fetchall()
                    require(
                        len(stored) == 1 and stored[0][:2] == ('completed', 'group_' + group),
                        'Incorrect persisted run identity',
                    )
                    require(bool(stored[0][2]), 'Persisted run has no source Bot')
                    bots_by_case[case].add(stored[0][2])
                    if case == 'memory_chat':
                        memory_events(db, run_id, row['turn'])
                        memory_turns['first_write' if row['turn'] == 1 else 'later_recall'] += 1
                    if 'box_exec' in catalogue[case]:
                        box_sessions[group].add(box_evidence(db, run_id, catalogue[case]))
        require(all(len(v) == 1 for v in bots_by_case.values()), 'Scenario unexpectedly changed source Bot')
        require(
            len({v for values in bots_by_case.values() for v in values}) == len(bots_by_case),
            'Scenarios share a source Bot',
        )
        require(all(len(v) == 1 for v in box_sessions.values()), 'A group did not reuse its own Box')
        require(
            len({v for values in box_sessions.values() for v in values}) == len(box_sessions),
            'Different groups shared a Box',
        )
        result['box_groups_verified'] = len(box_sessions)
        if 'memory_chat' in catalogue:
            result['memory_turns_verified'] = dict(memory_turns)
        warmups = {
            item['output']['data']['session_id']: item['case']
            for item in json.loads((root / 'warmup.json').read_text())
        }
        seen = defaultdict(set)
        model_paths = {WIRE[case][1]: (case, Path(provider_records[WIRE[case][0]]).resolve()) for case in catalogue}
        wire_counts = Counter()
        required_paths = {path for _, path in model_paths.values()}
        for path in {Path(path).resolve() for path in provider_records.values()}:
            if not path.is_file() and path not in required_paths:
                continue  # An unused mock service can legitimately have no generation log.
            for event in records(path):
                if event['path'] != '/v1/chat/completions':
                    continue
                request = event.get('request') or {}
                messages = request.get('messages') or []
                marked = [
                    (i, markers[-1])
                    for i, message in enumerate(messages)
                    if message.get('role') == 'user' and (markers := group_markers(message))
                ]
                if not marked:
                    continue
                # Native attachment reads append an unmarked typed user message
                # after the tool result. Attribute it to the triggering turn.
                position, marker = marked[-1]
                case, expected_path = model_paths.get(request.get('model'), (None, None))
                require(expected_path == path, 'Measured group request reached the wrong Provider/model')
                require(event.get('status') == 200 and event.get('response_complete'), 'Provider response incomplete')
                acknowledgement = group_ack(messages, position)
                group, turn, token = marker[0], int(marker[1]), marker[2]
                if group in warmups:
                    require(warmups[group] == case, 'Warmup reached wrong model')
                    continue
                row = tokens.get(token)
                require(
                    row is not None and (row['group_id'], row['turn'], row['case']) == (group, turn, case),
                    'Unowned or misrouted Provider request',
                )
                stage = sum(msg.get('role') == 'tool' for msg in messages[position + 1 :])
                last = final_stage(case, turn)
                if case == 'memory_chat':
                    select_message(request, memory_scenario())
                require(0 <= stage <= last and stage not in seen[token], 'Unexpected or repeated generation stage')
                seen[token].add(stage)
                wire_counts[case] += 1
                if stage == last:
                    content = (event.get('response') or {}).get('content')
                    require(content == catalogue[case]['expect'] + acknowledgement, 'Wrong final Provider response')
        if set(seen) != set(tokens) or any(
            seen[token] != set(range(final_stage(row['case'], row['turn']) + 1)) for token, row in tokens.items()
        ):
            raise MissingEvidence('Measured requests lack exact Provider stage receipts')
        below = [
            f'{name}: measured delivery {phase["delivery_ratio"]:.3f} below declared floor {phase["min_delivery_ratio"]:.3f}'
            for name, phase in result['phases'].items()
            if not phase['delivery_floor_passed']
        ]
        result.update(
            passed=not below,
            outcome='FAIL' if below else 'PASS',
            business_evidence_passed=True,
            delivery_floor_passed=not below,
            wire_stages=dict(wire_counts),
        )
        result['errors'].extend(below)
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        result['outcome'] = 'INCOMPLETE' if isinstance(exc, (MissingEvidence, FileNotFoundError, KeyError)) else 'FAIL'
        result['errors'].append(f'{type(exc).__name__}: {exc}')
    return result


def main():
    """Compile a scenario plan without starting services or touching a deployment."""
    import argparse

    from tools.entrypoints.regression_suite import validate

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--box-backend', choices=('docker', 'host'), default='docker')
    args = parser.parse_args()
    try:
        stock = Path(__file__).resolve().parents[1] / 'profiles' / 'endurance.json'
        profile = prepare_profile(json.loads(stock.read_text()), args.profile, box_backend=args.box_backend)
        validate(profile)
        print(
            json.dumps(
                {
                    'box_backend': args.box_backend,
                    'scenarios': sorted(case['name'] for case in profile['cases']),
                    'phases': [
                        {
                            **phase,
                            'offered_slots': planned_group_slots(
                                phase['duration_seconds'], phase['rps'], phase.get('max_requests')
                            ),
                        }
                        for phase in profile['phases']
                    ],
                },
                indent=2,
            )
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
