from langbot import __version__
from langbot_plugin.utils.version_compat import check

from ..api.application.contracts import ApplicationAPIError, ApplicationAPIException
from ..i18n import t


def compatibility(manifest):
    return check(manifest, __version__)


def incompatible(details):
    return ApplicationAPIException(
        ApplicationAPIError(
            'plugin_incompatible_langbot_version',
            t('No plugin version is compatible with this LangBot version'),
            409,
            details,
        )
    )


def compatible_release(detail):
    if not detail.get('compatible_version'):
        raise incompatible(dict(current=__version__, min=None, max=None, status='incompatible'))
    return detail['compatible_version']
