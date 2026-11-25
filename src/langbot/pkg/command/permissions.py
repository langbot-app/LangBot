from ..i18n import t


BUILTIN_GROUPS = {
    'session': ('help', 'new', 'stop', 'retry', 'undo'),
    'info': ('whoami', 'status', 'usage'),
    'admin': ('model', 'tools', 'plugins', 'version'),
}
PERMISSION_FIELDS = ('builtin', 'plugin_permissions', 'admins', 'denied_reply')


def builtin_settings(settings, name):
    defaults = {
        'enabled': name != 'model',
        'permission': 'everyone' if name in (*BUILTIN_GROUPS['session'], 'whoami') else 'admins',
    }
    return defaults | settings.get('builtin', {}).get(name, {})


def can_run(settings, permission, sender_id):
    return permission == 'everyone' or (permission == 'admins' and f'person_{sender_id}' in settings.get('admins', []))


def normalize_permissions(settings):
    def invalid():
        return ValueError(t('Invalid command permission settings'))

    result = {}
    if 'builtin' in settings:
        if not isinstance(settings['builtin'], dict):
            raise invalid()
        result['builtin'] = {}
        for names in BUILTIN_GROUPS.values():
            for name in names:
                if name not in settings['builtin']:
                    continue
                if not isinstance(settings['builtin'][name], dict):
                    raise invalid()
                config = builtin_settings(settings, name)
                if not isinstance(config['enabled'], bool) or config['permission'] not in ('everyone', 'admins'):
                    raise invalid()
                result['builtin'][name] = {key: config[key] for key in ('enabled', 'permission')}
    if 'admins' in settings:
        admins = settings['admins']
        if not isinstance(admins, list) or not all(isinstance(value, str) for value in admins):
            raise invalid()
        admins = [value.strip() for value in admins if value.strip()]
        if any(not value.startswith('person_') or not value[7:] for value in admins):
            raise invalid()
        result['admins'] = list(dict.fromkeys(admins))
    if 'denied_reply' in settings:
        if settings['denied_reply'] not in ('silent', 'notice'):
            raise invalid()
        result['denied_reply'] = settings['denied_reply']
    if 'plugin_permissions' in settings:
        permissions = settings['plugin_permissions']
        if not isinstance(permissions, dict) or any(
            not isinstance(key, str)
            or len(key.split('/')) != 3
            or not all(key.split('/'))
            or value not in ('everyone', 'admins')
            for key, value in permissions.items()
        ):
            raise invalid()
        result['plugin_permissions'] = dict(permissions)
    return result
