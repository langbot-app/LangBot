from __future__ import annotations

from langbot.pkg.kuku.runtime import _parse_hhmm, _unwrap_invoke_llm_result, in_quiet_hours


def test_in_quiet_hours_empty_config():
    assert in_quiet_hours({}) is False


def test_in_quiet_hours_missing_end():
    assert in_quiet_hours({'start': '09:00', 'timezone': 'UTC'}) is False


def test_parse_hhmm_valid_and_invalid():
    t = _parse_hhmm('09:30')
    assert t is not None
    assert t.hour == 9 and t.minute == 30
    assert _parse_hhmm('invalid') is None
    assert _parse_hhmm('25:00') is None


def test_unwrap_invoke_llm_tuple_vs_message():
    assert _unwrap_invoke_llm_result(('only', 'extra')) == 'only'
    assert _unwrap_invoke_llm_result('plain') == 'plain'
