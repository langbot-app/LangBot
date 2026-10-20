"""PLATFORM_API_MAP for LINE（EBA skeleton）。

对照 telegram/platform_api.py 與 slack/platform_api.py（逐 action 注册 callable）。
当前为空骨架——待 LINE Messaging API 端點實測後逐一定稿。
未實測的 action 一律先不注册，遵守 acceptance-checklist「未實測不声明」。
"""

from typing import Callable

PLATFORM_API_MAP: dict[str, Callable] = {
    # "send_message": ...,      # ⚠️待實測
    # "reply_message": ...,     # ⚠️待實測
    # "get_user_info": ...,     # ⚠️待實測
    # "get_group_info": ...,    # ⚠️待實測
    # "get_group_member_list": ...  # ⚠️待實測
}
