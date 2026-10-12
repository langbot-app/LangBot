from ...i18n import t


class RequesterError(Exception):
    """Base class for all Requester errors."""

    def __init__(self, message: str):
        super().__init__(t('Model request failed') + ': ' + message)
