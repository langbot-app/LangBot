from __future__ import annotations

import pytest

from langbot.pkg.api.http.controller.groups.box_visibility import should_hide_box_runtime_status


@pytest.mark.parametrize(
    ('edition', 'box_enabled', 'expected'),
    [
        ('cloud', False, True),
        ('cloud', True, False),
        ('cloud', None, False),
        ('community', False, False),
    ],
)
def test_should_hide_box_runtime_status(edition, box_enabled, expected):
    assert should_hide_box_runtime_status(edition, box_enabled) is expected
