from __future__ import annotations


class AccountEmailMismatchError(Exception):
    def __str__(self):
        return 'Account email mismatch'
