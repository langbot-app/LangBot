from __future__ import annotations


class OfficialAccountSendError(RuntimeError):
    def __init__(self, errcode: int):
        self.errcode = errcode
        reasons = {
            48001: 'Customer service API permission denied',
            45015: 'The 48-hour customer service reply window has expired',
            45047: 'Customer service message quota exceeded',
            43004: 'The user is not following the Official Account',
        }
        reason = reasons.get(errcode, 'Customer service message rejected')
        super().__init__(f'OfficialAccount send_message failed: errcode={errcode} ({reason})')


try:
    from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError
except ModuleNotFoundError:

    class NotSupportedError(Exception):
        def __init__(self, api_name: str, *args):
            super().__init__(f"API '{api_name}' is not supported by this adapter", *args)
            self.api_name = api_name
