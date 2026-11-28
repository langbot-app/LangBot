from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes


def message_received_event(query):
    hook = events.GroupMessageReceived if query.launcher_type == LauncherTypes.GROUP else events.PersonMessageReceived
    return hook(
        query=query,
        launcher_type=query.launcher_type.value,
        launcher_id=query.launcher_id,
        sender_id=query.sender_id,
        message_event=query.message_event,
        message_chain=query.message_chain,
    )
