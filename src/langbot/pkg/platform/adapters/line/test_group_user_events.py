# -*- coding: utf-8 -*-
"""
test_group_user_events.py — WO-LINE-04 群組與使用者事件擴充 selftest。

覆盖：
- target2yiri 事件映射（message/follow/unfollow/join/left/member_joined/member_left/postback/beacon/default）。
- PostbackEvent→platform.specific.postback（action + data）。
- supported_events（据 EBA 框架契约 + blueprint §3.2 映射表；未實測事件不宣告，architect §c 紅線）。
- LineGroupUserQuery API 映射（get_user_profile→get_user_info / get_group_summary→get_group_info / get_group_member_profile→get_group_member_list）。
- supported_apis（据 blueprint §3.4 LINE API→EBA 映射表）。
- _parse_event_timestamp（epoch 毫秒→秒）。

纪律标注：
- blueprint §3.2 明示 LINE 事件 JSON 映射 ⚠️待 LINE 事件 JSON 實測。
- blueprint §3.4 明示 LINE API→EBA 映射（含 getProfile / getGroupMemberIds 等）⚠️待 LINE Messaging API 端實測。
- 本测试仅验证**框架 + 命名空间映射**（据 blueprint §3.2/§3.4 + EBA 框架契约 + ops .84 SDK 实测框架）；
  未验证 SDK 实际调用（据 blueprint §3.2/§3.4 待實測）—— SDK 调用由 ops/architect 實測後定稿（§9/§23 禁捏造）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_extensions import LineEventExtensions, LineGroupUserQuery, _parse_event_timestamp


class TestEventMapping(unittest.TestCase):
    def setUp(self):
        self.ext = LineEventExtensions()

    def test_message_type(self):
        result = self.ext.target2yiri({'type': 'message', 'message': {'id': 'm1'}})
        self.assertEqual(result['type'], 'message.received')

    def test_follow_type(self):
        result = self.ext.target2yiri({'type': 'follow'})
        self.assertEqual(result['type'], 'user.followed')

    def test_unfollow_type(self):
        result = self.ext.target2yiri({'type': 'unfollow'})
        self.assertEqual(result['type'], 'user.unfollowed')

    def test_join_type(self):
        result = self.ext.target2yiri({'type': 'join'})
        self.assertEqual(result['type'], 'group.joined')

    def test_leave_type(self):
        result = self.ext.target2yiri({'type': 'left'})
        self.assertEqual(result['type'], 'group.left')

    def test_member_joined_type(self):
        result = self.ext.target2yiri({'type': 'member_joined'})
        self.assertEqual(result['type'], 'group.member_joined')

    def test_member_left_type(self):
        result = self.ext.target2yiri({'type': 'member_left'})
        self.assertEqual(result['type'], 'group.member_left')

    def test_postback_type(self):
        result = self.ext.target2yiri(
            {
                'type': 'postback',
                'data': {'action': 'buy', 'params': {'qty': 2}},
            }
        )
        self.assertEqual(result['type'], 'platform.specific.postback')
        self.assertEqual(result['action'], 'postback')
        self.assertEqual(result['params'], {'action': 'buy', 'params': {'qty': 2}})

    def test_beacon_type(self):
        result = self.ext.target2yiri({'type': 'beacon', 'data': {'ptype': 'enter'}})
        self.assertEqual(result['type'], 'platform.specific.beacon')

    def test_unknown_type_default_platform_specific(self):
        # 未映射者默认走 platform.specific（action = line.<type>），不宣告 capability
        result = self.ext.target2yiri({'type': 'unknown_type'})
        self.assertEqual(result['type'], 'platform.specific')
        self.assertEqual(result['action'], 'line.unknown_type')

    def test_non_dict_returns_none(self):
        self.assertIsNone(self.ext.target2yiri('not-a-dict'))


class TestSupportedEvents(unittest.TestCase):
    def test_supported_events_declaration(self):
        # 据 EBA 框架契约 + blueprint §3.2 映射表；未實測事件不宣告（architect §c 紅線）
        ext = LineEventExtensions()
        events = ext.supported_events()
        self.assertIn('message.received', events)
        self.assertIn('user.followed', events)
        self.assertIn('user.unfollowed', events)
        self.assertIn('group.joined', events)
        self.assertIn('group.left', events)
        self.assertIn('group.member_joined', events)
        self.assertIn('group.member_left', events)
        self.assertIn('platform.specific.postback', events)
        self.assertIn('platform.specific.beacon', events)


class TestGroupUserQuery(unittest.TestCase):
    def test_api_map(self):
        q = LineGroupUserQuery()
        # 据 blueprint §3.4 LINE API→EBA 映射表
        self.assertEqual(q.query_name('get_user_profile'), 'get_user_info')
        self.assertEqual(q.query_name('get_group_summary'), 'get_group_info')
        self.assertEqual(q.query_name('get_group_member_profile'), 'get_group_member_list')

    def test_api_map_unknown(self):
        q = LineGroupUserQuery()
        self.assertIsNone(q.query_name('not_a_real_api'))

    def test_supported_apis(self):
        q = LineGroupUserQuery()
        apis = q.supported_apis()
        # 据 blueprint §3.4 LINE API→EBA 映射表（可选）
        self.assertIn('get_user_info', apis)
        self.assertIn('get_group_info', apis)
        self.assertIn('get_group_member_list', apis)


class TestParseTimestamp(unittest.TestCase):
    def test_epoch_ms_converted_to_seconds(self):
        # ops .84 SDK 实测 LINE 事件多数用 epoch 毫秒
        self.assertAlmostEqual(_parse_event_timestamp(1700000000000), 1700000000.0)

    def test_epoch_seconds_passthrough(self):
        # 已过万（epoch 秒）不截断
        self.assertAlmostEqual(_parse_event_timestamp(1700000000), 1700000000.0)

    def test_none_returns_zero(self):
        self.assertEqual(_parse_event_timestamp(None), 0.0)


if __name__ == '__main__':
    unittest.main()
