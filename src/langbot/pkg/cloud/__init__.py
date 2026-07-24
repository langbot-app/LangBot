"""Contracts used by the optional closed Cloud control-plane bootstrap."""

from .bootstrap import (
    CloudBootstrapError,
    CloudManifestProvider,
    CloudManifestRefreshService,
    OpenSourceDeployment,
    VerifiedCloudDeployment,
    resolve_deployment,
)
from .directory import (
    DirectoryDelta,
    DirectoryEvent,
    DirectoryEventBatch,
    DirectoryMember,
    DirectoryProjectionProvider,
    DirectoryProjectionUnavailableError,
    DirectorySnapshot,
    DirectoryWorkspace,
)
from .directory_projection import DirectoryProjectionService
from .entitlements import (
    EntitlementProvider,
    EntitlementResolver,
    EntitlementSnapshot,
    EntitlementUnavailableError,
    OpenSourceEntitlementProvider,
)

__all__ = [
    'CloudBootstrapError',
    'CloudManifestProvider',
    'CloudManifestRefreshService',
    'DirectoryDelta',
    'DirectoryEvent',
    'DirectoryEventBatch',
    'DirectoryMember',
    'DirectoryProjectionProvider',
    'DirectoryProjectionService',
    'DirectoryProjectionUnavailableError',
    'DirectorySnapshot',
    'DirectoryWorkspace',
    'EntitlementProvider',
    'EntitlementResolver',
    'EntitlementSnapshot',
    'EntitlementUnavailableError',
    'OpenSourceDeployment',
    'OpenSourceEntitlementProvider',
    'VerifiedCloudDeployment',
    'resolve_deployment',
]
