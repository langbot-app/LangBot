from types import SimpleNamespace

import pytest

from langbot.pkg.agent.policy import _grant_allows


@pytest.mark.parametrize(
    ('grants', 'account', 'role', 'expected'),
    [
        ([], 'user-1', 'developer', False),
        ([SimpleNamespace(subject_type='role', subject_id='developer', can_use=True)], 'user-1', 'developer', True),
        ([SimpleNamespace(subject_type='role', subject_id='viewer', can_use=True)], 'user-1', 'developer', False),
        ([SimpleNamespace(subject_type='role', subject_id='developer', can_use=False)], 'user-1', 'developer', False),
        (
            [
                SimpleNamespace(subject_type='role', subject_id='developer', can_use=True),
                SimpleNamespace(subject_type='account', subject_id='user-1', can_use=False),
            ],
            'user-1',
            'developer',
            False,
        ),
        (
            [
                SimpleNamespace(subject_type='role', subject_id='developer', can_use=False),
                SimpleNamespace(subject_type='account', subject_id='user-1', can_use=True),
            ],
            'user-1',
            'developer',
            True,
        ),
    ],
)
def test_grant_matrix(grants, account, role, expected):
    assert _grant_allows(grants, account, role) is expected
