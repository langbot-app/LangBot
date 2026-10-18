"""Summarize explicit task run directories without exporting configs or credentials."""

import json
from pathlib import Path
import statistics
import sys


def summarize(root):
    result = {'run': root.name}
    if (root / 'metrics.json').exists():
        metrics = json.loads((root / 'metrics.json').read_text())
        result.update(
            sha=metrics['sha'],
            health=metrics['health'],
            survivors=metrics['survivors'],
            probe_exit=metrics.get('probe_exit_code'),
        )
        samples = metrics['samples']
        result['seconds'] = samples[-1]['seconds'] if samples else 0
        roles = {process['role'] for sample in samples for process in sample['processes']}
        result['resources'] = {}
        for role in sorted(roles):
            rows = [[p for p in sample['processes'] if p['role'] == role] for sample in samples]
            rss = [sum(p['rss'] for p in row) / 1024**2 for row in rows if row]
            cpu = [sum(p['cpu'] for p in row) for row in rows if row]
            result['resources'][role] = {
                'peak_rss_mib': round(max(rss), 2),
                'mean_sampled_cpu_percent': round(statistics.mean(cpu), 2),
            }
    if (root / 'matrix-result.json').exists():
        matrix = json.loads((root / 'matrix-result.json').read_text())
        result['matrix'] = {
            'complete': matrix.get('complete', False),
            'sent': matrix['sent'],
            'last_stage': matrix['stages'][-1]['label'],
        }
        result['matrix']['healthy_latency_from_fault_seconds'] = {}
        for kind, start in matrix.get('fault_started', {}).items():
            replies = [r for r in matrix.get('replies', []) if r['owner'] == 'healthy' and r['time'] >= start]
            result['matrix']['healthy_latency_from_fault_seconds'][kind] = (
                round(replies[0]['time'] - start, 3) if replies else None
            )
        last = matrix['stages'][-1]
        result['matrix']['final_query_pool'] = last['health']['resources']['query_pool']
        result['matrix']['final_message_states'] = last['message_states']
        result['matrix']['plugin_api_max_seconds'] = max(s['plugin_list']['seconds'] for s in matrix['stages'])
    return result


if __name__ == '__main__':
    print(json.dumps([summarize(Path(path)) for path in sys.argv[1:]], indent=2))
