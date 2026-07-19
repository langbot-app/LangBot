"""Contracts used by the optional closed Cloud control-plane bootstrap."""

from .bootstrap import (
    CloudBootstrapError,
    OpenSourceDeployment,
    VerifiedCloudDeployment,
    resolve_deployment,
)
from .entitlements import (
    EntitlementProvider,
    EntitlementResolver,
    EntitlementSnapshot,
    EntitlementUnavailableError,
    OpenSourceEntitlementProvider,
)

__all__ = [
    'CloudBootstrapError',
    'EntitlementProvider',
    'EntitlementResolver',
    'EntitlementSnapshot',
    'EntitlementUnavailableError',
    'OpenSourceDeployment',
    'OpenSourceEntitlementProvider',
    'VerifiedCloudDeployment',
    'resolve_deployment',
]
