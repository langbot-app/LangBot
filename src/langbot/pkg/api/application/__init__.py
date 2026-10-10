"""Versioned, workspace-scoped application APIs shared by protocol adapters."""

from .api import APPLICATION_API_VERSION, ApplicationAPI, OperationSpec

__all__ = ['APPLICATION_API_VERSION', 'ApplicationAPI', 'OperationSpec']
