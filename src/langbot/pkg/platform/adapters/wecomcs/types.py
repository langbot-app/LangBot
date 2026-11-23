from __future__ import annotations

ADAPTER_NAME = 'wecomcs-omni'


def make_private_chat_id(user_id: str | int | None, open_kfid: str | int | None) -> str:
    """Build the routable private chat id used by the WeCom CS Omni adapter."""
    user = str(user_id or '')
    kfid = str(open_kfid or '')
    if not user or not kfid:
        return user
    return f'{user}|{kfid}'


def parse_private_chat_id(chat_id: str | int) -> tuple[str, str]:
    user_id, sep, open_kfid = str(chat_id).partition('|')
    if not user_id or not sep or not open_kfid:
        raise ValueError('WeComCS target_id must be formatted as "external_userid|open_kfid"')
    return user_id, open_kfid


def split_private_chat_id(chat_id: str | int) -> tuple[str, str]:
    """Split a target id into (external_userid, open_kfid); open_kfid may be empty.

    Older sessions and the legacy pipeline launcher id carry only the customer's
    external_userid, so callers must resolve a missing open_kfid themselves.
    """
    user_id, sep, open_kfid = str(chat_id).strip().partition('|')
    user_id = user_id.strip()
    open_kfid = open_kfid.strip()
    if not user_id or (sep and not open_kfid):
        raise ValueError('WeComCS target_id must be formatted as "external_userid|open_kfid"')
    return user_id, open_kfid
