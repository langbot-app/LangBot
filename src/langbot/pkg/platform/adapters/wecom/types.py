from __future__ import annotations

ADAPTER_NAME = 'wecom-omni'


def make_private_chat_id(user_id: str | int | None, agent_id: str | int | None) -> str:
    """Build the routable private chat id used by the WeCom Omni adapter."""
    user = str(user_id or '')
    agent = str(agent_id or '')
    if not user or not agent:
        return user
    return f'{user}|{agent}'
