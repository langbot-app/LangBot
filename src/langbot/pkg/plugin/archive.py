from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from enum import Enum

import yaml


_PLUGIN_ARCHIVE_MAX_ENTRIES = 512
_PLUGIN_ARCHIVE_MAX_ENTRY_BYTES = 16 * 1024 * 1024
_PLUGIN_ARCHIVE_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_PLUGIN_ARCHIVE_MAX_COMPRESSION_RATIO = 100
_PLUGIN_METADATA_MAX_BYTES = 1024 * 1024
_PLUGIN_REQUIREMENTS_MAX_ENTRIES = 1000


class ArchiveCertificateState(str, Enum):
    """Syntactic certificate declaration state; this is not verification."""

    ABSENT = 'absent'
    MALFORMED = 'malformed'
    DECLARED = 'declared'


@dataclass(frozen=True)
class ArchiveCertificateDeclaration:
    """Bounded, verifier-facing certificate declaration from ``manifest.yaml``."""

    state: ArchiveCertificateState
    runtime_profile: str | None = None
    payload: dict[str, object] | None = None


@dataclass(frozen=True)
class PluginArchiveInspection:
    """Validated archive metadata plus unverified certificate declaration facts."""

    manifest: dict
    requirements: list[str]
    names: list[str]
    artifact_digest: str
    certificate: ArchiveCertificateDeclaration


def _read_plugin_archive_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    *,
    max_bytes: int = _PLUGIN_METADATA_MAX_BYTES,
) -> bytes:
    if member.file_size > max_bytes:
        raise ValueError(f'Plugin metadata file exceeds the {max_bytes}-byte limit: {member.filename}')
    with archive.open(member, 'r') as source:
        content = source.read(max_bytes + 1)
    if len(content) > max_bytes or len(content) != member.file_size:
        raise ValueError(f'Plugin metadata file has an invalid size: {member.filename}')
    return content


def _inspect_certificate_declaration(manifest: dict) -> ArchiveCertificateDeclaration:
    declaration = manifest.get('certification')
    if declaration is None:
        return ArchiveCertificateDeclaration(ArchiveCertificateState.ABSENT)
    if not isinstance(declaration, dict):
        return ArchiveCertificateDeclaration(ArchiveCertificateState.MALFORMED)

    runtime_profile = declaration.get('runtime_profile')
    payload = declaration.get('certificate')
    if not isinstance(runtime_profile, str) or not runtime_profile.strip() or not isinstance(payload, dict):
        return ArchiveCertificateDeclaration(ArchiveCertificateState.MALFORMED)
    return ArchiveCertificateDeclaration(
        ArchiveCertificateState.DECLARED,
        runtime_profile=runtime_profile,
        payload=payload,
    )


def inspect_plugin_archive(file_bytes: bytes, *, require_manifest: bool = True) -> PluginArchiveInspection:
    """Validate an archive and expose certificate declaration facts for a verifier.

    Certificate signatures and issuer trust are deliberately not evaluated here;
    callers must pass the declaration and artifact digest to an SDK verifier.
    """

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        members = archive.infolist()
        if len(members) > _PLUGIN_ARCHIVE_MAX_ENTRIES:
            raise ValueError('Plugin archive contains too many entries')

        total_uncompressed = 0
        files: dict[str, zipfile.ZipInfo] = {}
        names: list[str] = []
        for member in members:
            if member.is_dir():
                continue
            if member.flag_bits & 0x1:
                raise ValueError('Encrypted plugin archives are not supported')
            if member.file_size > _PLUGIN_ARCHIVE_MAX_ENTRY_BYTES:
                raise ValueError(f'Plugin archive entry exceeds the size limit: {member.filename}')
            if (
                member.file_size
                and member.file_size > max(member.compress_size, 1) * _PLUGIN_ARCHIVE_MAX_COMPRESSION_RATIO
            ):
                raise ValueError(f'Plugin archive entry exceeds the compression-ratio limit: {member.filename}')
            total_uncompressed += member.file_size
            if total_uncompressed > _PLUGIN_ARCHIVE_MAX_TOTAL_BYTES:
                raise ValueError('Plugin archive exceeds the uncompressed size limit')
            normalized = member.filename.replace('\\', '/').strip('/')
            names.append(member.filename)
            files.setdefault(normalized.lower(), member)

        manifest_member = files.get('manifest.yaml') or files.get('manifest.yml')
        if manifest_member is None:
            if require_manifest:
                raise ValueError('manifest.yaml is required')
            manifest = {}
        else:
            manifest = yaml.safe_load(_read_plugin_archive_member(archive, manifest_member).decode('utf-8')) or {}
        if not isinstance(manifest, dict):
            raise ValueError('Plugin manifest must be an object')

        requirements: list[str] = []
        requirements_member = next(
            (
                member
                for normalized, member in files.items()
                if normalized == 'requirements.txt' or normalized.endswith('/requirements.txt')
            ),
            None,
        )
        if requirements_member is not None:
            content = _read_plugin_archive_member(
                archive,
                requirements_member,
            ).decode(
                'utf-8',
                errors='ignore',
            )
            requirements = [
                line.strip()[:1000]
                for line in content.splitlines()
                if line.strip() and not line.strip().startswith('#')
            ][:_PLUGIN_REQUIREMENTS_MAX_ENTRIES]

        return PluginArchiveInspection(
            manifest=manifest,
            requirements=requirements,
            names=names,
            artifact_digest=hashlib.sha256(file_bytes).hexdigest(),
            certificate=_inspect_certificate_declaration(manifest),
        )


def inspect_plugin_archive_metadata(
    file_bytes: bytes,
    *,
    require_manifest: bool = True,
) -> tuple[dict, list[str], list[str]]:
    """Legacy tuple API for archive metadata callers.

    Use ``inspect_plugin_archive`` when certificate declaration facts are needed.
    """

    inspection = inspect_plugin_archive(file_bytes, require_manifest=require_manifest)
    return inspection.manifest, inspection.requirements, inspection.names
