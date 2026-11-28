"""Walk one path of a validated workflow and collect its step records."""

import asyncio
from datetime import datetime

from .graph import render, validate
from .steps import run_step


async def execute_tree(
    graph, message, *, ap, runtime, memory, save_memory, history, models, targets, issues=None, now=None
):
    if issues is None:
        issues = validate(graph, models=models, targets=targets)
    steps = []
    for issue in issues:
        if issue['severity'] == 'error':
            return steps, ': '.join(str(issue[key]) for key in ('node_id', 'field', 'code') if key in issue)

    nodes = {node['id']: node for node in graph['nodes']}
    edges = {(edge['from'], edge.get('branch')): edge['to'] for edge in graph['edges']}
    current = next(node['id'] for node in nodes.values() if node['type'] == 'start')
    results = {}
    try:
        async with asyncio.timeout(300):
            while current is not None:
                node = nodes[current]
                kind = node['type']
                step = dict(
                    seq=len(steps) + 1,
                    node_id=current,
                    node_type=kind,
                    node_name=node.get('name') or current,
                    inputs={},
                    outputs={},
                    branch=None,
                    started_at=datetime.now(),
                    status='failed',
                    error=None,
                )
                steps.append(step)
                inputs = {}
                try:
                    config = node['config']
                    if kind == 'code':
                        inputs = {
                            **render(
                                {key: value for key, value in config.items() if key != 'code'}, results, memory, now
                            ),
                            'code': config['code'],
                        }
                    else:
                        inputs = render(config, results, memory, now)
                    step['inputs'] = inputs
                    outputs, branch = await run_step(
                        kind,
                        inputs,
                        message,
                        ap=ap,
                        runtime=runtime,
                        memory=memory,
                        save_memory=save_memory,
                        history=history,
                        now=now,
                    )
                except Exception as exc:
                    step['error'] = str(exc) or type(exc).__name__
                    if kind not in ('llm', 'http') or inputs.get('on_error') != 'continue':
                        return steps, f'{step["node_name"]}: {step["error"]}'
                    outputs = {'text': ''} if kind == 'llm' else {'status': 0, 'body': '', 'json': None}
                    outputs['error'] = step['error']
                    branch = None
                finally:
                    step['finished_at'] = datetime.now()
                step.update(outputs=outputs, branch=branch)
                if kind in ('condition', 'http'):
                    step['error'] = outputs.get('error')
                if kind == 'http' and step['error'] and inputs.get('on_error') != 'continue':
                    return steps, f'{step["node_name"]}: {step["error"]}'
                step['status'] = 'failed' if kind != 'condition' and step['error'] else 'completed'
                results[current] = outputs
                current = edges.get((current, branch))
    except TimeoutError:
        if steps:
            steps[-1]['error'] = 'Workflow timed out after 300 seconds'
        return steps, 'Workflow timed out after 300 seconds'
    return steps, None
