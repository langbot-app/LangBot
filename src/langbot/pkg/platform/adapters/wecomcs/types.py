from __future__ import annotations

ADAPTER_NAME = 'wecomcs-eba'


def make_private_chat_id(user_id: str | int | None, open_kfid: str | int | None) -> str:
    """Build the routable private chat id used by the WeCom CS EBA adapter."""
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
