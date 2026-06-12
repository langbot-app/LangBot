from __future__ import annotations

from enum import Enum


class KookChannelType(str, Enum):
    GROUP = 'GROUP'
    PERSON = 'PERSON'


class KookMessageType(int, Enum):
    TEXT = 1
    IMAGE = 2
    FILE = 4
    AUDIO = 8
    KMARKDOWN = 9
    CARD = 10
