"""Runtime language isolation, catalog completeness, and Pipeline overrides."""

import asyncio
import json
import string
from pathlib import Path
from types import SimpleNamespace

import pytest

from langbot.pkg import i18n
from langbot.pkg.i18n.adapters import adapter_t, localized_adapter
from langbot.pkg.provider.modelmgr.errors import RequesterError


def test_catalogs_have_matching_keys_and_placeholders():
    folder = Path(i18n.__file__).parent / 'locales'
    catalogs = {
        locale: json.loads((folder / f'{locale}.json').read_text(encoding='utf-8'))
        for locale in i18n.SUPPORTED_LANGUAGES
    }
    english = catalogs['en_US']
    formatter = string.Formatter()

    def fields(text):
        return {name for _, name, _, _ in formatter.parse(text) if name is not None}

    for locale, catalog in catalogs.items():
        assert catalog.keys() == english.keys(), locale
        for key, text in catalog.items():
            assert text.strip(), (locale, key)
            assert fields(text) == fields(key), (locale, key)


@pytest.mark.asyncio
async def test_concurrent_requests_and_children_keep_their_language():
    async def render(locale):
        with i18n.language_scope(locale):

            async def child():
                await asyncio.sleep(0)
                return str(RequesterError(i18n.t('Request timed out')))

            return await asyncio.create_task(child())

    assert await asyncio.gather(render('zh_Hans'), render('ja_JP'), render('en_US')) == [
        '模型请求失败: 请求超时',
        'モデルへのリクエストに失敗しました: リクエストがタイムアウトしました',
        'Model request failed: Request timed out',
    ]
    assert i18n.language.get() == 'en_US'
    with pytest.raises(RuntimeError), i18n.language_scope('zh_Hans'):
        raise RuntimeError('interrupted')
    assert i18n.language.get() == 'en_US'


def test_pipeline_overrides_inherit_language_and_preserve_literal_braces():
    query = SimpleNamespace(pipeline_config={'output': {'misc': {}}})
    with i18n.language_scope('zh_Hans'):
        assert i18n.pipeline_notice(query, 'failure-hint', 'Request failed.') == '请求失败。'
        query.pipeline_config['output']['misc']['failure-hint'] = 'Request failed.'
        assert i18n.pipeline_notice(query, 'failure-hint', 'Request failed.') == '请求失败。'
        query.pipeline_config['output']['misc']['failure-hint'] = 'My custom notice {literal}'
        assert i18n.pipeline_notice(query, 'failure-hint', 'Request failed.') == 'My custom notice {literal}'
        query.pipeline_config['output']['misc']['tool-call-hint'] = 'Using {tools}; keep {other}'
        assert i18n.pipeline_notice(query, 'tool-call-hint', 'Calling {tools}...', tools='search') == (
            'Using search; keep {other}'
        )


def test_diagnostics_are_never_parsed_or_rewritten():
    diagnostic = 'upstream: {"error": "some provider detail"}'
    with i18n.language_scope('zh_Hans'):
        assert i18n.t(diagnostic) == diagnostic
        assert i18n.error_text('permission_denied', 'Missing Workspace permission: workspace.update') == (
            '没有执行此操作的权限'
        )
        assert i18n.t('Please do not replace model not found in user content') == (
            'Please do not replace model not found in user content'
        )


@pytest.mark.asyncio
async def test_adapter_callbacks_use_their_owner_not_the_callers_language():
    app = SimpleNamespace(_message_language_cache={'bot-workspace': ('ja_JP', float('inf'))})

    class Adapter:
        logger = SimpleNamespace(ap=app, execution_context=SimpleNamespace(workspace_uuid='bot-workspace'))

        @localized_adapter
        async def reply(self):
            return i18n.t('Submitted')

    with i18n.language_scope('zh_Hans'):
        assert await Adapter().reply() == '送信済み'
        assert adapter_t(Adapter(), 'Submitted') == '送信済み'
        assert i18n.language.get() == 'zh_Hans'


def test_lark_card_uses_selected_language():
    from langbot.pkg.platform.adapters.lark.stream_card import build_card

    with i18n.language_scope('ja_JP'):
        card = json.dumps(build_card('<think>reason</think>answer'), ensure_ascii=False)
        assert '思考過程' in card
        assert 'AI による生成コンテンツ' in card
        assert 'Thinking' not in card
