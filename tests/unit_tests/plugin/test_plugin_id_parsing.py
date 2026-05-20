"""Test plugin ID parsing validation."""

import pytest

from src.langbot.pkg.plugin.connector import PluginRuntimeConnector


def test_parse_plugin_id_accepts_author_name():
    assert PluginRuntimeConnector._parse_plugin_id('langbot/rag-engine') == ('langbot', 'rag-engine')


@pytest.mark.parametrize(
    'plugin_id',
    [
        '',
        'author',
        'author/',
        '/name',
        'author/name/extra',
        '/',
    ],
)
def test_parse_plugin_id_rejects_malformed_ids(plugin_id):
    with pytest.raises(ValueError, match='Expected'):
        PluginRuntimeConnector._parse_plugin_id(plugin_id)
