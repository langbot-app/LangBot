"""Principal-private Artifact operations with explicit installation grants."""

from __future__ import annotations

import base64
import binascii

from pydantic import Field, model_validator
from typing import Literal

from ..authz import Permission
from ..context import PrincipalType
from ...storage.artifacts import DEFAULT_TTL_SECONDS, MAX_ARTIFACT_BYTES, MAX_TTL_SECONDS
from .contracts import Input, Operation


class ArtifactCreate(Input):
    filename: str = Field(min_length=1, max_length=255)
    content: bytes | None = Field(default=None, max_length=MAX_ARTIFACT_BYTES)
    content_base64: str | None = Field(default=None, max_length=349528)
    mime_type: str = 'application/octet-stream'
    ttl_seconds: int = Field(default=DEFAULT_TTL_SECONDS, ge=1, le=MAX_TTL_SECONDS)

    @model_validator(mode='after')
    def exactly_one_content(self):
        if (self.content is None) == (self.content_base64 is None):
            raise ValueError('Supply exactly one of content or content_base64')
        if self.content_base64 is not None:
            try:
                content = base64.b64decode(self.content_base64, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError('Invalid Artifact base64 content') from exc
            if len(content) > 256 * 1024:
                raise ValueError('Artifact RPC content exceeds the 262144 byte limit')
        return self


class SkillResourceArtifactCreate(Input):
    skill_name: str = Field(min_length=1, max_length=64)
    revision: str = Field(min_length=1, max_length=71)
    path: str = Field(min_length=1, max_length=1024)
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
    values = payload.model_dump(exclude={'content_base64'})
    if payload.content_base64 is not None:
        try:
            values['content'] = base64.b64decode(payload.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('Invalid Artifact base64 content') from exc
        if len(values['content']) > 256 * 1024:
            raise ValueError('Artifact RPC content exceeds the 262144 byte limit')
    return await ap.artifact_service.create(context, **values)


async def create_skill_resource(ap, context, payload):
    return await ap.artifact_service.create_skill_resource(context, **payload.model_dump())


async def get(ap, context, payload):
    return await ap.artifact_service.get(context, payload.artifact_id)


async def read(ap, context, payload):
    result = await ap.artifact_service.read(context, payload.artifact_id, max_bytes=payload.max_bytes)
    if context.principal.principal_type == PrincipalType.PLUGIN:
        return {'metadata': result['metadata'], 'content_base64': base64.b64encode(result['content']).decode('ascii')}
    return result


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
    artifact_principals = principals | {PrincipalType.PLUGIN}
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
        Operation('artifact.create', manage, create, ArtifactCreate, dict, True, principals=artifact_principals),
        Operation(
            'artifact.skill_resource.create',
            manage,
            create_skill_resource,
            SkillResourceArtifactCreate,
            dict,
            True,
            principals=principals,
        ),
        Operation('artifact.get', view, get, ArtifactID, dict, principals=artifact_principals),
        Operation('artifact.read', view, read, ArtifactRead, dict, principals=artifact_principals),
        Operation(
            'artifact.read_content', view, read_content, ArtifactContent, list[dict], principals=artifact_principals
        ),
        Operation('artifact.retain', manage, retain, ArtifactID, dict, True, principals=artifact_principals),
        Operation('artifact.release', manage, release, ArtifactID, dict, True, principals=artifact_principals),
        Operation('artifact.delete', manage, delete, ArtifactID, dict, True, principals=artifact_principals),
    ]
