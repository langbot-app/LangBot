import pytest

from langbot.pkg.plugin.connector import _select_marketplace_plugin_version


@pytest.mark.parametrize(
    ('requested_version', 'expected'),
    [
        (None, '0.1.4'),
        ('0.1.3', '0.1.3'),
    ],
)
def test_select_marketplace_plugin_version(requested_version, expected):
    assert (
        _select_marketplace_plugin_version(
            [{'version': '0.1.4'}, {'version': '0.1.3'}],
            requested_version=requested_version,
            plugin_author='langbot-team',
            plugin_name='RunnerDemo',
        )
        == expected
    )


def test_select_marketplace_plugin_version_rejects_requested_missing_version():
    with pytest.raises(ValueError, match='version 0.1.2 is not available'):
        _select_marketplace_plugin_version(
            [{'version': '0.1.4'}],
            requested_version='0.1.2',
            plugin_author='langbot-team',
            plugin_name='RunnerDemo',
        )


@pytest.mark.parametrize('versions', [[], [{'unexpected': 'value'}], 'not-a-list'])
def test_select_marketplace_plugin_version_rejects_invalid_latest(versions):
    with pytest.raises(ValueError, match='has no versions'):
        _select_marketplace_plugin_version(
            versions,
            requested_version=None,
            plugin_author='langbot-team',
            plugin_name='RunnerDemo',
        )
