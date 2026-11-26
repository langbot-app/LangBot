from ..i18n import t


BUILTIN_GROUPS = {
    'session': ('help', 'new', 'stop', 'retry', 'undo'),
    'info': ('whoami', 'status', 'usage'),
    'admin': ('model', 'tools', 'plugins', 'version'),
}
PERMISSION_FIELDS = ('builtin', 'plugin_permissions', 'denied_reply')


def builtin_settings(settings, name):
    defaults = {
        'enabled': name != 'model',
        'permission': 'everyone' if name in (*BUILTIN_GROUPS['session'], 'whoami') else 'admins',
    }
    return defaults | settings.get('builtin', {}).get(name, {})


def can_run(permission, is_admin: bool):
    return permission == 'everyone' or (permission == 'admins' and is_admin)


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
