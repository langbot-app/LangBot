from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.core.notes.n001_classic_msgs import ClassicNotes


@pytest.mark.parametrize(
    'space, expected',
    [
        ({}, True),
        ({'disable_release_check': False}, True),
        ({'disable_release_check': True}, False),
        ({'disable_release_check': 'false'}, True),
        ({'disable_release_check': 'TrUe'}, False),
    ],
)
async def test_release_check_is_enabled_by_default_but_offline_instances_can_disable_it(space, expected):
    version = SimpleNamespace(show_version_update=AsyncMock(return_value=('test release note', 20)))
    app = SimpleNamespace(instance_config=SimpleNamespace(data={'space': space}), ver_mgr=version)
    note = ClassicNotes(app)
    assert await note.need_show() is expected
    if expected:
        assert [result async for result in note.yield_note()] == [('test release note', 20)]
        version.show_version_update.assert_awaited_once()
    else:
        version.show_version_update.assert_not_awaited()
