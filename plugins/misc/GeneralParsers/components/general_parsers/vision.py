from __future__ import annotations

import base64
import re
from typing import Awaitable, Callable

InvokeVision = Callable[[str, str], Awaitable[str]]

OCR_PAGE_PROMPT = '请识别并提取这张图片中的所有文字内容，保持原始排版。'
ANALYZE_IMAGE_PROMPT = (
    '请识别这张图片中的可见文字；如果图片还包含图表、界面、照片或其他重要视觉信息，'
    '请用简洁语言补充描述。只输出识别结果，不要添加额外解释。'
)

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_VISION_REFUSAL_PATTERNS = (
    "i don't have the ability to see or analyze images",
    "i do not have the ability to see or analyze images",
    "i can't see or analyze images",
    "i cannot see or analyze images",
    "no image was attached",
    "what can i help you with",
    "我无法查看图片",
    "我无法直接查看图片",
    "我不能查看图片",
    "没有附加图片",
    "没有附加到你的消息",
    "如果你愿意我帮助",
    "what you'd like me to help with",
)


def encode_image_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode('ascii')


def sanitize_vision_text(text: str) -> str:
    """Strip chain-of-thought and common refusal boilerplate from vision output."""
    cleaned = _THINK_TAG_RE.sub("", text).strip()
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    if any(pattern in lowered for pattern in _VISION_REFUSAL_PATTERNS):
        return ""

    cleaned = re.sub(r"^\[(?:图片描述|image description)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.rstrip(" ]")
    return cleaned.strip()
