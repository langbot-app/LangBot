from langbot import __version__
from langbot_plugin.utils.version_compat import check

from ..api.application.contracts import ApplicationAPIError, ApplicationAPIException
from ..i18n import t


def compatibility(manifest):
    return check(manifest, __version__)


def incompatible(details, message):
    return ApplicationAPIException(
        ApplicationAPIError(
            'plugin_incompatible_langbot_version',
            message,
            409,
            details,
        )
    )


def incompatible_package(details):
    return incompatible(
        details,
        t(
            'The declared LangBot version range is incompatible with the current version ({current})',
            current=details['current'],
        ),
    )


def compatible_release(detail):
    if not detail.get('compatible_version'):
        raise incompatible(
            dict(current=__version__, min=None, max=None, status='incompatible'),
            t('No plugin version is compatible with this LangBot version'),
        )
    return detail['compatible_version']
