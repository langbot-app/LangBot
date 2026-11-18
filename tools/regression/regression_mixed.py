"""Independent wire and persisted-run evidence for the mixed endurance workload."""

from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3

from tools.entrypoints.mock_llm import GROUP_TURN, group_ack


MODELS = {'chat': 'mock-chat', 'box': 'mock-smoke-box', 'rag_chat': 'mock-rag'}
BOX_HOST = re.compile(r'^LB_BOX_HOST=([A-Za-z0-9_.-]+)$', re.MULTILINE)
RECOVERY_QUEUES = (
    'core.body.resources.query_pool.queued',
    'box.body.resources.blocking_executor.pending',
    'box.body.resources.creating_session_tasks',
    'box.body.resources.closing_session_tasks',
)


class MissingEvidence(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def interval(start, end):
    if not start or not end:
        raise MissingEvidence('Persisted execution timestamps are missing')
    values = tuple(datetime.fromisoformat(value).timestamp() for value in (start, end))
    require(values[0] < values[1], 'Execution interval is empty or reversed')
    return values


def overlaps(left, right):
    return max(left[0], right[0]) < min(left[1], right[1])


def service_interval(record):
    start, duration = record.get('time'), record.get('duration_seconds')
    if (
        any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
            for value in (start, duration)
        )
        or duration == 0
    ):
        raise MissingEvidence('Provider request needs its recorded start and measured duration')
    return start, start + duration


def verify_mixed(output_suite_dir, ledger_db, provider_records):
    """Fail closed on wrong identities; report the concurrency evidence actually observed."""
    root = Path(output_suite_dir)
    result = {'passed': False, 'outcome': 'INCOMPLETE', 'errors': [], 'counts': {}, 'box_tool_event_overlap': None}
    try:
        require(set(provider_records) == set(MODELS), 'Three named Provider record streams are required')
        require(
            len({Path(path).resolve() for path in provider_records.values()}) == 3, 'Provider streams must be distinct'
        )
        rows, phases = [], {}
        for path in sorted(root.glob('*/requests.jsonl')):
            rows.extend({**row, 'phase': path.parent.name} for row in records(path))
            phases[path.parent.name] = json.loads(path.with_name('summary.json').read_text())
        if not rows:
            raise MissingEvidence('No measured group request records')
        recovery = {}
        for name, summary in phases.items():
            queues = summary.get('resource_observations', {}).get('queues', {})
            recovery[name] = {}
            for metric in RECOVERY_QUEUES:
                observed = queues.get(metric, {})
                value = observed.get('cooldown_tail_max')
                if observed.get('status') != 'observed' or (
                    isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                ):
                    raise MissingEvidence(f'{name}: cooldown recovery evidence missing for {metric}')
                require(value == 0, f'{name}: cooldown queue did not drain: {metric}={value}')
                recovery[name][metric] = value
        result['cooldown_recovery'] = recovery
        tokens, runs = {}, set()
        groups, bots, box_hosts = defaultdict(list), defaultdict(set), defaultdict(set)
        tool_intervals = []
        with sqlite3.connect(Path(ledger_db).resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            for row in rows:
                case, token, group = row['case'], row.get('token'), row.get('group_id')
                require(case in MODELS and row['status'] == 'ok', 'Every measured mixed request must succeed')
                if not token or not group or not row.get('run', {}).get('run_id'):
                    raise MissingEvidence('A request lacks its original token, group or verified run')
                run_id = row['run']['run_id']
                require(token not in tokens and run_id not in runs, 'Requests share a token or AgentRun')
                tokens[token] = row
                runs.add(run_id)
                found = db.execute(
                    'SELECT run_id, status, conversation_id, bot_id, started_at, finished_at FROM agent_run WHERE run_id=?',
                    (run_id,),
                ).fetchall()
                require(len(found) == 1, 'Request does not identify exactly one persisted AgentRun')
                run = dict(found[0])
                require(run['status'] == 'completed', 'Persisted mixed AgentRun is not completed')
                require(run['conversation_id'] == 'group_' + group, 'Persisted run belongs to another group')
                require(bool(run['bot_id']), 'Persisted run has no source Bot')
                bots[case].add(run['bot_id'])
                row['execution_interval'] = interval(run['started_at'], run['finished_at'])
                require(row['seconds'] > 0, 'HTTP execution duration is missing')
                row['http_interval'] = (row['elapsed'], row['elapsed'] + row['seconds'])
                groups[group].append(row)
                if case != 'box':
                    continue
                starts, hosts, completed_ids = {}, set(), set()
                for kind, raw, created in db.execute(
                    'SELECT type, data_json, created_at FROM agent_run_event WHERE run_id=? ORDER BY sequence',
                    (run_id,),
                ):
                    data = json.loads(raw or '{}')
                    if data.get('tool_name') != 'exec':
                        continue
                    call_id = data.get('tool_call_id')
                    require(isinstance(call_id, str) and bool(call_id), 'Box exec event has no call identity')
                    if kind == 'tool.call.started':
                        require(call_id not in starts and call_id not in completed_ids, 'Box exec start is duplicated')
                        starts[call_id] = created
                    elif kind == 'tool.call.completed':
                        require(call_id not in completed_ids, 'Box exec completion is duplicated')
                        completed_ids.add(call_id)
                        output = data.get('result', {})
                        require(output.get('backend') == 'docker' and output.get('exit_code') == 0, 'Box exec failed')
                        matches = BOX_HOST.findall(output.get('stdout', ''))
                        require(len(matches) == 1, 'Each Box exec must report exactly one actual hostname')
                        hosts.add(matches[0])
                        began = starts.pop(call_id, None)
                        tool_intervals.append((row, interval(began, created), matches[0]))
                if starts or len(completed_ids) != 2:
                    raise MissingEvidence('Each Box run needs two paired exec event windows')
                require(len(hosts) == 1, 'A Box run changed hostname')
                box_hosts[group].update(hosts)
        require(set(bots) == set(MODELS), 'All three business paths must execute')
        require(all(len(values) == 1 for values in bots.values()), 'One business path unexpectedly changed source Bot')
        require(len(set.union(*bots.values())) == 3, 'Business paths did not originate from three distinct Bots')
        require(all(len(items) >= 2 for items in groups.values()), 'Every observed group must complete multiple turns')
        require(len(box_hosts) >= 2, 'At least two Box groups must execute')
        require(all(len(values) == 1 for values in box_hosts.values()), 'A group did not reuse its Box across turns')
        require(len(set.union(*box_hosts.values())) == len(box_hosts), 'Different Box groups shared a Box hostname')
        warmup_path = root / 'warmup.json'
        warmups = (
            {item['output']['data']['session_id']: item['case'] for item in json.loads(warmup_path.read_text())}
            if warmup_path.exists()
            else {}
        )
        matched = defaultdict(set)
        wire_counts, provider_intervals = {}, defaultdict(list)
        for case, path in provider_records.items():
            count = 0
            for record in records(path):
                if record.get('path') != '/v1/chat/completions':
                    continue
                messages = record.get('request', {}).get('messages', [])
                positions = [i for i, message in enumerate(messages) if message.get('role') == 'user']
                if not positions:
                    continue
                position = positions[-1]
                markers = list(GROUP_TURN.finditer(str(messages[position].get('content', ''))))
                if not markers:
                    continue  # Preparation probes have no measured group identity.
                marker = markers[-1]
                require(record['request']['model'] == MODELS[case], 'Provider received the wrong model')
                require(
                    record.get('status') == 200 and record.get('response_complete'), 'Model response was incomplete'
                )
                if marker[1] in warmups:
                    require(warmups[marker[1]] == case, 'Warmup reached the wrong Provider')
                    group_ack(messages, position)
                    continue
                row = tokens.get(marker[3])
                require(row is not None, 'Provider received an unowned group token')
                require(row['case'] == case and marker[1] == row['group_id'], 'Request reached the wrong Provider')
                require(int(marker[2]) == row['turn'], 'Provider received the wrong group turn')
                acknowledgement = group_ack(messages, position)
                stage = sum(message.get('role') == 'tool' for message in messages[position + 1 :])
                expected_stages = {0, 1, 2} if case == 'box' else {0}
                require(
                    stage in expected_stages and stage not in matched[marker[3]],
                    'Model request stage is duplicated or unexpected',
                )
                matched[marker[3]].add(stage)
                if stage == max(expected_stages):
                    expected = {'chat': 'LANGBOT_CHAT_OK', 'box': 'LANGBOT_BOX_OK', 'rag_chat': 'LANGBOT_RAG_OK'}[case]
                    require(
                        record.get('response', {}).get('content') == expected + acknowledgement,
                        'Provider final response identifies the wrong request',
                    )
                provider_intervals[case].append((row['phase'], service_interval(record)))
                count += 1
            require(count > 0, 'A Provider has no measured generation requests')
            wire_counts[case] = count
        require(set(matched) == set(tokens), 'Measured requests are missing from the Provider wire evidence')
        require(
            all(stages == ({0, 1, 2} if tokens[token]['case'] == 'box' else {0}) for token, stages in matched.items()),
            'Measured requests have missing model stages',
        )
        provider_overlap = {}
        for case, observed in provider_intervals.items():
            found = next(
                (
                    (peer, left, right)
                    for peer, values in provider_intervals.items()
                    if peer != case
                    for left in observed
                    for right in values
                    if left[0] == right[0] and overlaps(left[1], right[1])
                ),
                None,
            )
            require(found is not None, f'Provider {case} never served generation concurrently with another Provider')
            peer, left, right = found
            provider_overlap[case] = {
                'peer': peer,
                'phase': left[0],
                'overlap_seconds': min(left[1][1], right[1][1]) - max(left[1][0], right[1][0]),
            }
        result['provider_service_overlap'] = provider_overlap
        result['provider_timing_scope'] = (
            'Every generation Provider overlaps another Provider, using recorded HTTP service intervals; '
            'this does not require all three to overlap at one instant.'
        )
        box_rows = [row for row in rows if row['case'] == 'box']
        paired = None
        for left in box_rows:
            for right in box_rows:
                if left['group_id'] == right['group_id'] or left['phase'] != right['phase']:
                    continue
                if overlaps(left['http_interval'], right['http_interval']) and overlaps(
                    left['execution_interval'], right['execution_interval']
                ):
                    paired = [left['run']['run_id'], right['run']['run_id']]
                    break
            if paired:
                break
        require(paired is not None, 'Different Box groups never overlapped in both HTTP and persisted execution')
        result['box_tool_event_overlap'] = any(
            left[0]['group_id'] != right[0]['group_id']
            and left[0]['phase'] == right[0]['phase']
            and left[2] != right[2]
            and overlaps(left[1], right[1])
            for left in tool_intervals
            for right in tool_intervals
        )
        require(result['box_tool_event_overlap'], 'Persisted Box exec event windows were entirely serialized')
        result.update(
            passed=True,
            outcome='PASS',
            counts={'requests': len(rows), 'groups': len(groups), 'bots': 3, 'box_groups': len(box_hosts)},
            provider_requests=wire_counts,
            box_hosts={group: next(iter(hosts)) for group, hosts in box_hosts.items()},
            box_http_and_agent_run_overlap=paired,
            timing_scope='Persisted tool event windows include scheduling and transport; they are not CPU timings.',
        )
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
        result['outcome'] = 'INCOMPLETE' if isinstance(exc, (MissingEvidence, FileNotFoundError)) else 'FAIL'
    return result
