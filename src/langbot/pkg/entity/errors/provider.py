from __future__ import annotations


class RequesterNotFoundError(Exception):
    def __init__(self, requester_name: str):
        self.requester_name = requester_name

    def __str__(self):
        return f'Requester {self.requester_name} not found'
