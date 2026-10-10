import pytest

from langbot.pkg.platform.adapters.wecombot.stream_text import format_stream_text


def test_multiple_rounds_have_one_thinking_section_and_separated_answers():
    raw = '<think>one</think>Checking.<think>two</think>More checks.<think>three</think>Done.'
    result = format_stream_text(raw)
    assert result == '<think>\none\n\ntwo\n\nthree\n</think>\n\nChecking.\n\nMore checks.\n\nDone.'
    assert format_stream_text(result) == result


@pytest.mark.parametrize('suffix', ['<', '<t', '<thi', '<think', '</', '</thi'])
def test_partial_tags_are_not_shown_in_answer(suffix):
    result = format_stream_text('<think>one</think>Checking.' + suffix)
    assert result.endswith('Checking.')


def test_later_incomplete_thinking_remains_inside_single_section():
    result = format_stream_text('<think>one</think>Checking.<think>two')
    assert result == '<think>\none\n\ntwo\n</think>\n\nChecking.'


def test_plain_markdown_is_unchanged():
    text = '  hello\n\n```python\na < b\n```\n'
    assert format_stream_text(text) == text


def test_initial_partial_thinking_tag_waits_for_next_snapshot():
    assert format_stream_text('<thi') == ''
