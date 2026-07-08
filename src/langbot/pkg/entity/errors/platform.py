from __future__ import annotations


class AdapterNotFoundError(Exception):
    def __init__(self, adapter_name: str):
        self.adapter_name = adapter_name

    def __str__(self):
        return f'Adapter {self.adapter_name} not found'
