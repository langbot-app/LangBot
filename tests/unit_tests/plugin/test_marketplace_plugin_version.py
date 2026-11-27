import pytest
from langbot.pkg.api.application.contracts import ApplicationAPIException

from langbot.pkg.plugin.connector import _select_marketplace_plugin_version


def test_select_latest_compatible_release():
    options = dict(plugin_author='test', plugin_name='probe', requested_version=None)
    assert _select_marketplace_plugin_version([], detail={'compatible_version': '1.2'}, **options) == '1.2'
    with pytest.raises(ApplicationAPIException) as error:
        _select_marketplace_plugin_version([{'version': '9.0'}], detail={'compatible_version': None}, **options)
    assert error.value.error.code == 'plugin_incompatible_langbot_version'
    assert error.value.error.message == 'No plugin version is compatible with this LangBot version'


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
