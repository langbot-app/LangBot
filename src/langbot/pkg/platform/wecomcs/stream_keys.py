from __future__ import annotations


def build_pull_stream_name(bot_uuid: str, shard: int) -> str:
    return f"wecomcs:{bot_uuid}:pull-trigger:{shard}"


def build_process_stream_name(bot_uuid: str, shard: int) -> str:
    return f"wecomcs:{bot_uuid}:message-process:{shard}"


def build_retry_zset_key(bot_uuid: str) -> str:
    return f"wecomcs:{bot_uuid}:retry"


def build_pull_consumer_group_name(base_group: str, bot_uuid: str) -> str:
    return f"{base_group}:{bot_uuid}"


def build_process_consumer_group_name(base_group: str, bot_uuid: str) -> str:
    return f"{base_group}:{bot_uuid}"
