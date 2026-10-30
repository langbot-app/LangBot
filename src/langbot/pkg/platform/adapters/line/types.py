from __future__ import annotations

ADAPTER_NAME = 'line-omni'

# LINE Messaging API limits (push/reply share the same message array budget).
MAX_MESSAGES_PER_REQUEST = 5

# A single text message body is limited to 5000 characters.
MAX_TEXT_LENGTH = 5000

# LINE serves inbound media through the Blob API; keep the same cap as the legacy adapter.
MAX_LINE_MEDIA_BYTES = 10 * 1024 * 1024
