"""OAuth errors with stable HTTP response codes."""


class OAuthError(ValueError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


class TotpHandoffRequired(OAuthError):
    def __init__(self, ticket: str):
        super().__init__('totp_required', 428)
        self.ticket = ticket
