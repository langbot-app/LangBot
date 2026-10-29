"""Bind the real Application API to focused consumer test applications."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langbot.pkg.api.application import ApplicationAPI


@asynccontextmanager
async def _tenant_scope(workspace_uuid):
    yield


def bind_application_api(ap, context):
    """Fill missing execution infrastructure while preserving real test services."""
    if getattr(ap, 'workspace_service', None) is None:
        ap.workspace_service = SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid=context.instance_uuid,
                    workspace_uuid=context.workspace_uuid,
                    placement_generation=context.placement_generation,
                )
            )
        )
    if getattr(ap, 'persistence_mgr', None) is None:
        ap.persistence_mgr = SimpleNamespace(tenant_scope=_tenant_scope)
    elif getattr(ap.persistence_mgr, 'tenant_scope', None) is None:
        ap.persistence_mgr.tenant_scope = _tenant_scope
    ap.application_api = ApplicationAPI(ap)
    return ap.application_api
