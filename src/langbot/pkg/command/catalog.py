from ..i18n import SUPPORTED_LANGUAGES, t
from .permissions import BUILTIN_GROUPS, builtin_settings


DESCRIPTIONS = {
    'help': 'List available commands',
    'new': 'Start a new conversation',
    'stop': 'Stop the current reply',
    'retry': 'Regenerate the last reply',
    'undo': 'Remove the last turn',
    'whoami': 'Show sender and session IDs',
    'status': 'Show session status',
    'usage': 'Show session usage',
    'model': 'Show or change the session model',
    'tools': 'List available tools',
    'plugins': 'List enabled plugins',
    'version': 'Show the LangBot version',
}


def builtin_commands():
    return [
        {
            'name': name,
            'group': group,
            'aliases': ['reset'] if name == 'new' else [],
            'default_enabled': builtin_settings({}, name)['enabled'],
            'default_permission': builtin_settings({}, name)['permission'],
            'label': {locale: '/' + name for locale in SUPPORTED_LANGUAGES},
            'description': {locale: t(DESCRIPTIONS[name], locale=locale) for locale in SUPPORTED_LANGUAGES},
        }
        for group, names in BUILTIN_GROUPS.items()
        for name in names
    ]
