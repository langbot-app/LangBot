"""Canonical names for built-in Omni adapters and saved pre-release configs."""

OMNI_ADAPTER_NAMES = frozenset(
    {
        'telegram',
        'discord',
        'qqofficial',
        'lark',
        'dingtalk',
        'slack',
        'kook',
        'wecom',
        'wecombot',
        'wecomcs',
        'officialaccount',
    }
)


def canonical_adapter_name(name: str) -> str:
    """Accept previous built-in IDs without renaming legacy or custom adapters."""
    if name in ('aiocqhttp-omni', 'aiocqhttp-eba'):
        return 'onebot-v11'
    if name.endswith('-eba') and name[:-4] in OMNI_ADAPTER_NAMES:
        return f'{name[:-4]}-omni'
    return name
