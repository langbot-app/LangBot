"""Account/API-key Artifact operations; plugin and run access is opt-in later."""

from __future__ import annotations

from pydantic import Field
from typing import Literal

from ..authz import Permission
from ..context import PrincipalType
from ...storage.artifacts import DEFAULT_TTL_SECONDS, MAX_ARTIFACT_BYTES, MAX_TTL_SECONDS
from .contracts import Input, Operation


class ArtifactCreate(Input):
    filename: str = Field(min_length=1, max_length=255)
    content: bytes = Field(max_length=MAX_ARTIFACT_BYTES)
    mime_type: str = 'application/octet-stream'
    ttl_seconds: int = Field(default=DEFAULT_TTL_SECONDS, ge=1, le=MAX_TTL_SECONDS)


class ArtifactID(Input):
    artifact_id: str = Field(min_length=1, max_length=64)


class ArtifactRead(ArtifactID):
    max_bytes: int = Field(default=MAX_ARTIFACT_BYTES, ge=1, le=MAX_ARTIFACT_BYTES)


class ArtifactContent(ArtifactID):
    mode: Literal['auto', 'text', 'native', 'pages'] = 'auto'
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=8192, ge=1, le=16384)
    page_start: int = Field(default=1, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class ArtifactPublicationInput(Input):
    producer_type: Literal['agent', 'pipeline', 'event_processor']
    producer_id: str = Field(min_length=1, max_length=255)


class ArtifactPublicationSet(ArtifactPublicationInput):
    enabled: bool


async def publication_get(ap, context, payload):
    return await ap.artifact_publication_service.get(context, **payload.model_dump())


async def publication_set(ap, context, payload):
    return await ap.artifact_publication_service.set(context, **payload.model_dump())


async def publication_disable(ap, context, payload):
    return await ap.artifact_publication_service.disable(context, **payload.model_dump())


async def create(ap, context, payload):
    return await ap.artifact_service.create(context, **payload.model_dump())


async def get(ap, context, payload):
    return await ap.artifact_service.get(context, payload.artifact_id)


async def read(ap, context, payload):
    return await ap.artifact_service.read(context, payload.artifact_id, max_bytes=payload.max_bytes)


async def read_content(ap, context, payload):
    return await ap.artifact_service.read_content(context, **payload.model_dump())


async def retain(ap, context, payload):
    return await ap.artifact_service.retain(context, payload.artifact_id)


async def release(ap, context, payload):
    return await ap.artifact_service.release(context, payload.artifact_id)


async def delete(ap, context, payload):
    return await ap.artifact_service.delete(context, payload.artifact_id)


def operations():
    principals = frozenset({PrincipalType.ACCOUNT, PrincipalType.API_KEY})
    view, manage = Permission.RESOURCE_VIEW, Permission.RESOURCE_MANAGE
    return [
        Operation(
            'artifact.publication.get', view, publication_get, ArtifactPublicationInput, dict, principals=principals
        ),
        Operation(
            'artifact.publication.set',
            manage,
            publication_set,
            ArtifactPublicationSet,
            dict,
            True,
            principals=principals,
        ),
        Operation(
            'artifact.publication.disable',
            manage,
            publication_disable,
            ArtifactPublicationInput,
            dict,
            True,
            principals=principals,
        ),
        Operation('artifact.create', manage, create, ArtifactCreate, dict, True, principals=principals),
        Operation('artifact.get', view, get, ArtifactID, dict, principals=principals),
        Operation('artifact.read', view, read, ArtifactRead, dict, principals=principals),
        Operation('artifact.read_content', view, read_content, ArtifactContent, list[dict], principals=principals),
        Operation('artifact.retain', manage, retain, ArtifactID, dict, True, principals=principals),
        Operation('artifact.release', manage, release, ArtifactID, dict, True, principals=principals),
        Operation('artifact.delete', manage, delete, ArtifactID, dict, True, principals=principals),
    ]
