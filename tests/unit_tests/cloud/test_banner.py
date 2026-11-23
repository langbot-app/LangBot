from types import SimpleNamespace

import pytest

from langbot.pkg.cloud.banner import resolve_cloud_banner


def cloud_app(config: dict | None = None, mode: str = 'cloud'):
    return SimpleNamespace(
        deployment=SimpleNamespace(mode=mode),
        instance_config=SimpleNamespace(data=config or {}),
    )


def banner_config(**overrides) -> dict:
    banner = {
        'enabled': True,
        'level': 'maintenance',
        'content': {
            'zh_Hans': '  服务维护中  ',
            'en_US': 'Service maintenance in progress',
        },
    }
    banner.update(overrides)
    return {'cloud': {'banner': banner}}


def test_cloud_banner_resolves_configured_copy():
    banner = resolve_cloud_banner(cloud_app(banner_config()))

    assert banner is not None
    assert banner['level'] == 'maintenance'
    assert banner['content'] == {
        'zh_hans': '服务维护中',
        'en_us': 'Service maintenance in progress',
    }
    # Defaults remain available for the inline links.
    assert banner['show_links'] is True
    assert banner['dismissible'] is True
    assert banner['dedicated_url'] == 'https://space.langbot.app/cloud?environment=dedicated'
    assert banner['repository_url'] == 'https://github.com/langbot-app/LangBot'


def test_cloud_banner_is_cloud_only():
    assert resolve_cloud_banner(cloud_app(banner_config(), mode='oss')) is None


def test_cloud_banner_needs_the_switch():
    assert resolve_cloud_banner(cloud_app(banner_config(enabled=False))) is None
    assert resolve_cloud_banner(cloud_app({})) is None
    assert resolve_cloud_banner(cloud_app({'cloud': {'banner': 'true'}})) is None


def test_cloud_banner_accepts_string_switch_from_environment():
    # ``CLOUD__BANNER__ENABLED=true`` on an instance whose config.yaml has no
    # banner block lands as the string 'true' instead of a boolean.
    banner = resolve_cloud_banner(cloud_app({'cloud': {'banner': {'enabled': 'true', 'content': {'en_US': 'x'}}}}))

    assert banner is not None
    assert banner['content'] == {'en_us': 'x'}


def test_cloud_banner_normalizes_level_and_links():
    banner = resolve_cloud_banner(
        cloud_app(
            {
                'cloud': {
                    'banner': {
                        'enabled': True,
                        'level': 'LOUD',
                        'show_links': False,
                        'dismissible': False,
                        'dedicated_url': 'javascript:alert(1)',
                        'repository_url': 'https://example.com/repo',
                        'content': {'en_US': 'notice'},
                    }
                }
            }
        )
    )

    assert banner is not None
    assert banner['level'] == 'info'
    assert banner['show_links'] is False
    assert banner['dismissible'] is False
    # A non-web URL never reaches the rendered link.
    assert banner['dedicated_url'] == 'https://space.langbot.app/cloud?environment=dedicated'
    assert banner['repository_url'] == 'https://example.com/repo'


def test_cloud_banner_drops_empty_copy():
    banner = resolve_cloud_banner(
        cloud_app({'cloud': {'banner': {'enabled': True, 'content': {'zh_Hans': '   ', 'en_US': ''}}}})
    )

    assert banner is not None
    assert banner['content'] == {}


@pytest.mark.parametrize('language', ['zh-Hans', 'zh_hant', 'EN_us', 'ja-JP', 'ru-RU'])
def test_cloud_banner_language_keys_are_underscored(language: str):
    banner = resolve_cloud_banner(
        cloud_app({'cloud': {'banner': {'enabled': True, 'content': {language: 'copy'}}}})
    )

    assert banner is not None
    assert list(banner['content']) == [language.strip().lower().replace('-', '_')]
