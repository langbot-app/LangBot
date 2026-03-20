from __future__ import annotations

import json
import typing

import langbot_plugin.api.entities.builtin.provider.message as provider_message


def format_result_log(
    result: provider_message.Message | provider_message.MessageChunk,
    cut_str: typing.Callable[[str], str],
) -> str | None:
    if result.tool_calls:
        tool_names = [tc.function.name for tc in result.tool_calls if tc.function and tc.function.name]
        if tool_names:
            return f'{result.role}: requested tools: {", ".join(tool_names)}'
        return f'{result.role}: requested tool calls'

    content = result.content
    if isinstance(content, str):
        if not content.strip():
            return None

        if result.role == 'tool':
            if content.startswith('err:'):
                return f'tool error: {cut_str(content)}'

            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                return cut_str(result.readable_str())

            if isinstance(payload, dict):
                status = payload.get('status', 'unknown')
                exit_code = payload.get('exit_code')
                backend = payload.get('backend', '')
                stdout = str(payload.get('stdout', '')).strip()
                summary = f'tool result: status={status}'
                if exit_code is not None:
                    summary += f' exit_code={exit_code}'
                if backend:
                    summary += f' backend={backend}'
                if stdout:
                    summary += f' stdout={cut_str(stdout)}'
                return summary

        return cut_str(result.readable_str())

    if isinstance(content, list) and len(content) == 0:
        return None

    return cut_str(result.readable_str())
