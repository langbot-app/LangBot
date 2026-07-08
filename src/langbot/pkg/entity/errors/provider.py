from __future__ import annotations


class RequesterNotFoundError(Exception):
    def __init__(self, requester_name: str):
        self.requester_name = requester_name

    def __str__(self):
        return f'Requester {self.requester_name} not found'


class ProviderNotFoundError(Exception):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    def __str__(self):
        return f'Provider {self.provider_name} not found'
