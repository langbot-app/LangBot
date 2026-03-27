from __future__ import annotations

import hashlib


def _stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)


def resolve_pull_shard(bot_uuid: str, open_kfid: str, shard_count: int) -> int:
    if shard_count <= 0:
        raise ValueError("pull shard_count must be greater than 0")
    route_key = f"{bot_uuid}:{open_kfid}"
    return _stable_hash(route_key) % shard_count


def resolve_process_shard(bot_uuid: str, open_kfid: str, external_userid: str, shard_count: int) -> int:
    if shard_count <= 0:
        raise ValueError("process shard_count must be greater than 0")
    route_key = f"{bot_uuid}:{open_kfid}:{external_userid}"
    return _stable_hash(route_key) % shard_count
