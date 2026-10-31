from __future__ import annotations


class AccountEmailMismatchError(Exception):
    def __str__(self) -> str:
        return 'Account email mismatch'


class SpaceAccountNotRegisteredError(AccountEmailMismatchError):
    code = 'space_account_not_registered'

    def __str__(self) -> str:
        return 'No Account is registered for this Space email'


class SpaceAccountBindingRequiredError(AccountEmailMismatchError):
    code = 'space_account_binding_required'

    def __str__(self) -> str:
        return 'This local account must bind a LangBot Account from Account settings before LangBot Account login'
