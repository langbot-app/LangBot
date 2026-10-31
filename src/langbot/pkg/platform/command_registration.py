from __future__ import annotations

import dataclasses
import hashlib
import json
import typing

import regex
from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent


class PlatformCommandEvent(MessageReceivedEvent):
    platform_command: bool = True
    command_name: str
    command_args: str = ''


@dataclasses.dataclass(frozen=True)
class CommandRegistrationCapability:
    max_commands: int
    name_pattern: str
    description_max_length: int
    multilingual: bool
    scopes: bool
    lowercase: bool = False


TELEGRAM_COMMANDS = CommandRegistrationCapability(100, r'[a-z0-9_]{1,32}', 256, True, True)
DISCORD_COMMANDS = CommandRegistrationCapability(
    100, r'[-_\u02BC\p{L}\p{N}\p{sc=Deva}\p{sc=Thai}]{1,32}', 100, True, True, True
)
TELEGRAM_LOCALES = {
    'en_US': 'en',
    'zh_Hans': 'zh',
    'zh_Hant': 'zh',
    'ja_JP': 'ja',
    'es_ES': 'es',
    'ru_RU': 'ru',
    'vi_VN': 'vi',
    'th_TH': 'th',
}
DISCORD_LOCALES = {
    'en_US': 'en-US',
    'zh_Hans': 'zh-CN',
    'zh_Hant': 'zh-TW',
    'ja_JP': 'ja',
    'es_ES': 'es-ES',
    'ru_RU': 'ru',
    'vi_VN': 'vi',
    'th_TH': 'th',
}


@typing.runtime_checkable
class PlatformCommandRegistrar(typing.Protocol):
    @staticmethod
    def command_registration_capability() -> CommandRegistrationCapability: ...

    async def sync_platform_commands(self, specs: dict[str, list[dict]]) -> dict: ...


def descriptions(manifest: typing.Any) -> dict[str, str]:
    value = getattr(manifest.metadata, 'description', None)
    if hasattr(value, 'to_dict'):
        value = value.to_dict()
    if isinstance(value, str):
        return {'en_US': value}
    return {
        key.replace('-', '_'): text for key, text in (value or {}).items() if isinstance(text, str) and text.strip()
    }


def build_command_plan(
    settings: dict, manifests: list, plugin_ids: list[str], capability: CommandRegistrationCapability, language: str
) -> dict:
    language = language.replace('-', '_')
    selected = set(settings.get('platform_commands', {}).get('selected', []))
    effective = {}
    for plugin_id in plugin_ids:
        for manifest in manifests:
            if manifest.owner == plugin_id:
                effective.setdefault(manifest.metadata.name, manifest)
    commands = []
    rejected = []
    available = []
    for name, manifest in effective.items():
        localized = descriptions(manifest)
        description = localized.get(language) or localized.get('en_US') or next(iter(localized.values()), '')
        reason = None
        if not regex.fullmatch(capability.name_pattern, name) or (capability.lowercase and name.lower() != name):
            reason = 'invalid_name'
        elif not description or len(description) > capability.description_max_length:
            reason = 'invalid_description'
        elif any(len(text) > capability.description_max_length for text in localized.values()):
            reason = 'invalid_localized_description'
        elif name in selected and len(commands) >= capability.max_commands:
            reason = 'command_limit'
        available.append({'name': name, 'description': description, 'reason': reason})
        if reason:
            rejected.append({'name': name, 'reason': reason})
        elif name in selected:
            commands.append({'name': name, 'description': description, 'descriptions': localized})
    rejected.extend({'name': name, 'reason': 'unavailable'} for name in sorted(selected - effective.keys()))
    if not settings.get('enabled', True) or not settings.get('platform_commands', {}).get('enabled', False):
        commands = []
    return {
        'capability': dataclasses.asdict(capability),
        'commands': commands,
        'available': available,
        'rejected': rejected,
    }


def command_sets(plan: dict, adapter_name: str, language: str) -> dict[str, list[dict]]:
    commands = plan['commands']
    result = {'': [{'name': item['name'], 'description': item['description']} for item in commands]}
    locales = TELEGRAM_LOCALES if adapter_name == 'telegram' else DISCORD_LOCALES
    preferred = language.replace('-', '_')
    ordered_locales = [locale for locale in locales if locale != preferred] + (
        [preferred] if preferred in locales else []
    )
    for locale in ordered_locales:
        if any(locale in item['descriptions'] for item in commands):
            result[locales[locale]] = [
                {'name': item['name'], 'description': item['descriptions'].get(locale, item['description'])}
                for item in commands
            ]
    return result


def command_set_hash(specs: dict) -> str:
    return hashlib.sha256(json.dumps(specs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
