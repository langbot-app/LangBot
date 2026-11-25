import pytest

from langbot.pkg.persistence.session_summary_contract import build_monitoring_session_id, parse_group_member_id


@pytest.mark.parametrize(
    ('group', 'sender', 'key'),
    [
        ('team_a', 'b', 'groupmember_6_team_a_b'),
        ('team', 'a_b', 'groupmember_4_team_a_b'),
        ('群:_聊', ' 人:_甲 ', 'groupmember_4_群:_聊_人:_甲'),
    ],
)
def test_roundtrip(group, sender, key):
    assert build_monitoring_session_id('group', group, sender) == key
    assert parse_group_member_id(key) == (group, sender.strip())


@pytest.mark.parametrize(
    'key', ['group_x_y', 'groupmember_x_a_b', 'groupmember_2_a_b', 'groupmember_1_a_', 'groupmember_01_a_b']
)
def test_invalid_member(key):
    assert parse_group_member_id(key) is None
