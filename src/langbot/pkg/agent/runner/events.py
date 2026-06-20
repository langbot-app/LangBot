"""Canonical AgentRunner event names reserved for future EBA integration."""
from __future__ import annotations


MESSAGE_RECEIVED = 'message.received'
"""A normal message entered the current Pipeline."""

MESSAGE_RECALLED = 'message.recalled'
"""A platform message was recalled or deleted."""

GROUP_MEMBER_JOINED = 'group.member_joined'
"""A new member joined a group/channel conversation."""

FRIEND_REQUEST_RECEIVED = 'friend.request_received'
"""A new friend/contact request was received."""


RESERVED_EVENT_TYPES = frozenset(
    {
        MESSAGE_RECEIVED,
        MESSAGE_RECALLED,
        GROUP_MEMBER_JOINED,
        FRIEND_REQUEST_RECEIVED,
    }
)
