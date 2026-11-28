from collections import OrderedDict
import threading


def is_wechatpad_message(event: object) -> bool:
    if not isinstance(event, dict):
        return False

    sender = event.get('from_user_name')
    return isinstance(sender, dict) and bool(sender.get('str'))


def is_wechatpad_text_message(event: object) -> bool:
    return isinstance(event, dict) and is_wechatpad_message(event) and event.get('msg_type') == 1


def is_wechatpad_friend_request(event: object) -> bool:
    return isinstance(event, dict) and is_wechatpad_message(event) and event.get('msg_type') == 37


class WeChatPadMessageDeduplicator:
    def __init__(self, max_entries: int = 4096):
        if max_entries < 1:
            raise ValueError('max_entries must be greater than zero')

        self.max_entries = max_entries
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _message_key(event: dict) -> str | None:
        for field in ('new_msg_id', 'msg_id'):
            value = event.get(field)
            if value not in (None, '', 0, '0'):
                return f'{field}:{value}'
        return None

    def is_duplicate(self, event: dict) -> bool:
        key = self._message_key(event)
        if key is None:
            return False

        with self._lock:
            if key in self._seen:
                self._seen.move_to_end(key)
                return True

            self._seen[key] = None
            if len(self._seen) > self.max_entries:
                self._seen.popitem(last=False)
            return False
