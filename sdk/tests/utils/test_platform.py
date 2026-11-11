import sys

from langbot_plugin.utils.platform import get_platform


def test_get_platform_returns_current_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "test-platform")

    assert get_platform() == "test-platform"
