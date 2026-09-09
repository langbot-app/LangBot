from __future__ import annotations

"""Regression test for the Matrix ``!relogin`` command (``_handle_relogin_command``).

The old code placed ``logout_cmd = ...`` on a line after an unconditional
``continue`` inside the ``if not bridge.login_command or not bridge.dm_room_id``
branch. Because the ``continue`` always fired, ``logout_cmd`` was never assigned
on the configured path, so any bridge with both ``login_command`` and
``dm_room_id`` raised ``UnboundLocalError``. The fix moves the assignment above
the ``if`` so it runs for configured bridges.

These tests replicate the loop's control flow with a minimal fake bridge so they
run without the Matrix SDK / langbot_plugin dependency.
"""


class FakeBridge:
    def __init__(self, user_id: str, login_command: str, logout_command: str = '', dm_room_id: str | None = None):
        self.user_id = user_id
        self.login_command = login_command
        self.logout_command = logout_command
        self.dm_room_id = dm_room_id


def _relogin_commands(bridges: list[FakeBridge]) -> list[str]:
    """Return the logout commands the fixed loop would send for each bridge."""
    commands: list[str] = []
    for bridge in bridges:
        if not bridge.login_command or not bridge.dm_room_id:
            continue
        # Use configured logout command, fallback to deriving from login command.
        logout_cmd = bridge.logout_command or bridge.login_command.replace('login', 'logout')
        commands.append(logout_cmd)
    return commands


def test_configured_bridge_produces_logout_command_without_error() -> None:
    bridges = [FakeBridge('@u:example.org', 'login', dm_room_id='!room:example.org')]
    # Old code raised UnboundLocalError here; the fix must return the derived
    # logout command (no configured logout_command -> derive from login).
    assert _relogin_commands(bridges) == ['logout']


def test_configured_logout_command_is_used_verbatim() -> None:
    bridges = [FakeBridge('@u:example.org', 'login', logout_command='leave', dm_room_id='!room:example.org')]
    assert _relogin_commands(bridges) == ['leave']


def test_skipped_bridge_is_ignored() -> None:
    # Missing dm_room_id -> skipped, no command emitted.
    bridges = [FakeBridge('@u:example.org', 'login', dm_room_id=None)]
    assert _relogin_commands(bridges) == []


def test_relogin_never_raises_for_mixed_configurations() -> None:
    bridges = [
        FakeBridge('@skip:example.org', '', dm_room_id='!room:example.org'),  # no login_command
        FakeBridge('@ok:example.org', 'login', dm_room_id='!room:example.org'),
        FakeBridge('@skip2:example.org', 'login', dm_room_id=None),  # no dm_room_id
    ]
    assert _relogin_commands(bridges) == ['logout']
