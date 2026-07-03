from __future__ import annotations

ADAPTER_NAME = 'wecomcs-eba'


def make_private_chat_id(user_id: str | int | None, open_kfid: str | int | None) -> str:
    """Build the routable private chat id used by the WeCom CS EBA adapter."""
    user = str(user_id or '')
    kfid = str(open_kfid or '')
    if not user or not kfid:
        return user
    return f'{user}|{kfid}'


def _strip_legacy_user_prefix(user_id: str) -> str:
    if user_id.startswith('u'):
        return user_id[1:]
    return user_id


def _looks_like_open_kfid(value: str) -> bool:
    return value.startswith(('kf', 'wk', 'open_kfid'))


def parse_private_chat_id(chat_id: str | int, default_open_kfid: str | int | None = None) -> tuple[str, str]:
    raw = str(chat_id)
    left, sep, right = raw.partition('|')
    if sep:
        if _looks_like_open_kfid(left) or right.startswith('u'):
            open_kfid, user_id = left, right
        else:
            user_id, open_kfid = left, right
    else:
        user_id = raw
        open_kfid = str(default_open_kfid or '')
    user_id = _strip_legacy_user_prefix(str(user_id or ''))
    open_kfid = str(open_kfid or '')
    if not user_id or not open_kfid:
        raise ValueError('WeComCS target_id must include external_userid and open_kfid')
    return user_id, open_kfid
