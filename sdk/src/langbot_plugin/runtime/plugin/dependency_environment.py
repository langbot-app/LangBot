from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import shutil
import stat
import tempfile
import time
import typing
import weakref
from collections.abc import Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from langbot_plugin.runtime.plugin.artifact import PluginArtifact


_ENVIRONMENT_SCHEMA_VERSION = 3
_READY_MARKER = ".ready.json"
_MAX_REQUIREMENTS_BYTES = 1024 * 1024
_MAX_REQUIREMENT_COUNT = 1024
_MAX_ENVIRONMENT_ENTRIES = 100_000
_MAX_ENVIRONMENT_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_PROVIDED_DISTRIBUTIONS = frozenset({"langbot-plugin"})
_RUNTIME_SDK_COMPATIBILITY_SERIES = (0, 6)
# Raw archive SHA-256 digests, not normalized certification digests. This is
# dependency ABI admission only; it never grants certification or shared slots.
# Releases that reviewed the nine digest-pinned legacy archives below. A new
# Runtime release re-verifies dedicated behavior before extending this set.
_LEGACY_DEDICATED_SDK_RUNTIME_VERSIONS = frozenset({"0.7.4", "0.7.5", "0.7.6"})

_LEGACY_DEDICATED_SDK_061 = {
    (
        "langbot-team",
        "CozeAgent",
        "0.1.10",
    ): "90d9e1adbf456fd5e55ab8e022c26a17d272bf834104d711fff390c3649dc7a4",
    (
        "langbot-team",
        "DashScopeAgent",
        "0.1.10",
    ): "ca9fe3b6cf3d891c0d5f5ef6c711c25b20a922e8fe110778997314a1f8b0559e",
    (
        "langbot-team",
        "DeerFlowAgent",
        "0.1.10",
    ): "b35f551f9a9498f1f33d2596230725d3db1f13852edcb74330bc4a4dd681c6c9",
    (
        "langbot-team",
        "DifyAgent",
        "0.1.10",
    ): "1dd9cb4140bf0c2f848ecd648210b8cf7c9a0f520575ddc61e91a704e3ea3280",
    (
        "langbot-team",
        "LangflowAgent",
        "0.1.10",
    ): "b582250f2bf46e758fd904c52dea0ee6496626d61be6096a44fb9b34684583a5",
    (
        "langbot-team",
        "N8nAgent",
        "0.1.10",
    ): "0eee26b0101d166385425049727c0bf433582615d507fa36efc456b78cecac4a",
    (
        "langbot-team",
        "TboxAgent",
        "0.1.8",
    ): "387a02a2bed698b04f119042bab19c2400e53a433c6f0451a566e4c33807896f",
    (
        "langbot-team",
        "WeKnoraAgent",
        "0.1.10",
    ): "95dddd70a6f768660bd2de3adaebbe585b3aa42de7ad6ddb5a9fb6777590c9cc",
    (
        "langbot-team",
        "LocalAgent",
        "0.1.10",
    ): "a08a3f33cc10f5292d5ebafa58af1b993c8b89dbe6692df7895e924ffdd88da3",
}


class DependencyEnvironmentPreparationError(RuntimeError):
    """A stable, user-safe failure raised before an artifact worker is launched."""


@dataclass(frozen=True, slots=True)
class PluginDependencyEnvironment:
    """One immutable dependency tree shared by workers for the same environment."""

    digest: str
    artifact_digest: str
    requirements_digest: str
    runtime_fingerprint: str
    root_path: pathlib.Path
    site_packages_path: pathlib.Path


@dataclass(frozen=True, slots=True)
class DependencyEnvironmentStaging:
    """Runtime-owned writable paths visible only to the preparation sandbox."""

    root_path: pathlib.Path
    site_packages_path: pathlib.Path
    scratch_path: pathlib.Path
    jail_root_path: pathlib.Path
    tmp_path: pathlib.Path


DependencyInstaller = Callable[
    [DependencyEnvironmentStaging, Sequence[str]], Awaitable[None]
]


class PluginDependencyEnvironmentStore:
    """Atomically prepare and publish immutable per-artifact dependency trees."""

    def __init__(
        self,
        base_path: str | os.PathLike = "data/plugin-runtime",
        *,
        metrics: typing.Any | None = None,
    ):
        self.base_path = pathlib.Path(base_path)
        self.environments_path = self.base_path / "environments" / "sha256"
        self.metrics = metrics
        self._prepare_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    async def prepare(
        self,
        artifact: PluginArtifact,
        *,
        runtime_fingerprint: str,
        installer: DependencyInstaller,
        execution_mode: str | None = None,
    ) -> PluginDependencyEnvironment:
        requirements, requirements_digest = self._read_requirements(
            artifact, execution_mode=execution_mode
        )
        digest = self._environment_digest(
            artifact.digest,
            requirements_digest,
            runtime_fingerprint,
        )
        expected = self._metadata(
            digest=digest,
            artifact_digest=artifact.digest,
            requirements_digest=requirements_digest,
            runtime_fingerprint=runtime_fingerprint,
        )

        ready = self.get_ready(digest, expected=expected)
        if ready is not None:
            self._record_cache_hit()
            return ready

        lock = self._prepare_locks.setdefault(digest, asyncio.Lock())
        async with lock:
            ready = self.get_ready(digest, expected=expected)
            if ready is not None:
                self._record_cache_hit()
                return ready
            self._record_cache_miss()
            started_at = time.monotonic()
            try:
                return await self._prepare_locked(
                    artifact,
                    digest=digest,
                    expected=expected,
                    requirements=requirements,
                    installer=installer,
                )
            except BaseException:
                if self.metrics is not None:
                    self.metrics.dependency_prepare_failures_total += 1
                raise
            finally:
                elapsed = max(time.monotonic() - started_at, 0.0)
                if self.metrics is not None:
                    self.metrics.dependency_prepare_seconds_total += elapsed
                    self.metrics.dependency_prepare_seconds_last = elapsed

    def _record_cache_hit(self) -> None:
        if self.metrics is not None:
            self.metrics.dependency_cache_hits_total += 1

    def _record_cache_miss(self) -> None:
        if self.metrics is not None:
            self.metrics.dependency_cache_misses_total += 1

    def get_ready(
        self,
        digest: str,
        *,
        expected: dict[str, object] | None = None,
    ) -> PluginDependencyEnvironment | None:
        if _SHA256_PATTERN.fullmatch(str(digest or "")) is None:
            return None
        root_path = self.environments_path / digest
        marker_path = root_path / _READY_MARKER
        site_packages_path = root_path / "site-packages"
        try:
            metadata = json.loads(marker_path.read_text(encoding="utf-8"))
            root_mode = stat.S_IMODE(root_path.stat().st_mode)
            site_mode = stat.S_IMODE(site_packages_path.stat().st_mode)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if not isinstance(metadata, dict) or metadata.get("digest") != digest:
            return None
        if expected is not None and metadata != expected:
            return None
        if not site_packages_path.is_dir():
            return None
        if root_mode & 0o222 or site_mode & 0o222:
            return None
        try:
            return PluginDependencyEnvironment(
                digest=digest,
                artifact_digest=str(metadata["artifact_digest"]),
                requirements_digest=str(metadata["requirements_digest"]),
                runtime_fingerprint=str(metadata["runtime_fingerprint"]),
                root_path=root_path,
                site_packages_path=site_packages_path,
            )
        except KeyError:
            return None

    async def _prepare_locked(
        self,
        artifact: PluginArtifact,
        *,
        digest: str,
        expected: dict[str, object],
        requirements: Sequence[str],
        installer: DependencyInstaller,
    ) -> PluginDependencyEnvironment:
        def create_staging() -> DependencyEnvironmentStaging:
            self.environments_path.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o700,
            )
            temporary_root = pathlib.Path(
                tempfile.mkdtemp(
                    prefix=f".{digest}.",
                    dir=self.environments_path,
                )
            )
            staging = DependencyEnvironmentStaging(
                root_path=temporary_root,
                site_packages_path=temporary_root / "site-packages",
                scratch_path=temporary_root / ".scratch",
                jail_root_path=temporary_root / ".scratch" / "root",
                tmp_path=temporary_root / ".scratch" / "tmp",
            )
            try:
                staging.site_packages_path.mkdir(mode=0o700)
                staging.jail_root_path.mkdir(parents=True, mode=0o700)
                staging.tmp_path.mkdir(mode=0o700)
            except BaseException:
                shutil.rmtree(temporary_root, ignore_errors=True)
                raise
            return staging

        staging = create_staging()
        temporary_root = staging.root_path

        try:
            await installer(staging, requirements)
            # Validate structure before reading distribution metadata: a build
            # backend is untrusted and could otherwise make the Runtime follow
            # a link outside the staging tree while verifying its output.
            self._validate_tree_entries(staging.site_packages_path)
            self._validate_installed_requirements(
                staging.site_packages_path,
                requirements,
            )
            shutil.rmtree(staging.scratch_path)
            self._make_tree_read_only(staging.site_packages_path)
            self._write_marker(temporary_root / _READY_MARKER, expected)

            target_root = self.environments_path / digest
            try:
                os.rename(temporary_root, target_root)
            except OSError:
                # Another Runtime process may have completed the exact same
                # environment while this process was preparing its staging tree.
                ready = self.get_ready(digest, expected=expected)
                if ready is None:
                    raise
                shutil.rmtree(temporary_root, ignore_errors=True)
                return ready
            # macOS requires the source directory to be writable for rename.
            # get_ready rejects this tree until its root is sealed below.
            target_root.chmod(0o555)
            self._fsync_directory(self.environments_path)

            ready = self.get_ready(digest, expected=expected)
            if ready is None:  # pragma: no cover - publication invariant
                raise RuntimeError("Dependency environment publication failed")
            return ready
        except BaseException:
            shutil.rmtree(temporary_root, ignore_errors=True)
            raise

    @staticmethod
    def _runtime_sdk_requirement_satisfied(
        requirement: Requirement,
        runtime_version: str,
    ) -> bool:
        if not requirement.specifier or requirement.specifier.contains(
            runtime_version,
            prereleases=True,
        ):
            return True

        # Published 0.6 plugins historically used exact SDK pins even though
        # workers always import the Runtime-owned SDK. Preserve that deployed
        # contract only within the reviewed 0.6 compatibility series: an older
        # exact pin is a minimum ABI level, while every other constraint remains
        # strict. Direct URLs are rejected before this helper is called.
        specifiers = tuple(requirement.specifier)
        if len(specifiers) != 1 or specifiers[0].operator != "==":
            return False
        requested_raw = specifiers[0].version
        if "*" in requested_raw:
            return False
        try:
            requested = Version(requested_raw)
            runtime = Version(runtime_version)
        except InvalidVersion:
            return False
        return (
            requested.release[:2] == _RUNTIME_SDK_COMPATIBILITY_SERIES
            and runtime.release[:2] == _RUNTIME_SDK_COMPATIBILITY_SERIES
            and requested <= runtime
        )

    @staticmethod
    def _read_requirements(
        artifact: PluginArtifact,
        *,
        execution_mode: str | None = None,
    ) -> tuple[tuple[str, ...], str]:
        requirements_path = artifact.code_path / "requirements.txt"
        try:
            with requirements_path.open("rb") as requirements_file:
                content = requirements_file.read(_MAX_REQUIREMENTS_BYTES + 1)
        except FileNotFoundError:
            content = b""
        except OSError as exc:
            raise DependencyEnvironmentPreparationError(
                "Plugin dependency declarations are unavailable"
            ) from exc
        if len(content) > _MAX_REQUIREMENTS_BYTES:
            raise DependencyEnvironmentPreparationError(
                "Plugin requirements.txt exceeds the artifact Runtime limit"
            )
        requirements_digest = hashlib.sha256(content).hexdigest()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DependencyEnvironmentPreparationError(
                "Plugin requirements.txt must be UTF-8"
            ) from exc

        requirements: list[str] = []
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-"):
                raise DependencyEnvironmentPreparationError(
                    "Artifact requirements.txt cannot contain pip options "
                    f"(line {line_number})"
                )
            try:
                requirement = Requirement(line)
            except InvalidRequirement as exc:
                raise DependencyEnvironmentPreparationError(
                    "Artifact requirements.txt contains an invalid requirement "
                    f"(line {line_number})"
                ) from exc
            canonical_name = canonicalize_name(requirement.name)
            if canonical_name in _RUNTIME_PROVIDED_DISTRIBUTIONS:
                if requirement.marker is not None and not requirement.marker.evaluate():
                    continue
                if requirement.url:
                    raise DependencyEnvironmentPreparationError(
                        "Runtime-provided dependency langbot-plugin cannot use a direct URL"
                    )
                try:
                    runtime_version = importlib.metadata.version(requirement.name)
                except importlib.metadata.PackageNotFoundError as exc:
                    raise DependencyEnvironmentPreparationError(
                        "Runtime-provided dependency langbot-plugin is unavailable"
                    ) from exc
                # Validate the already-installed Runtime SDK, including beta
                # releases, rather than filtering candidates for installation.
                compatible = (
                    PluginDependencyEnvironmentStore._runtime_sdk_requirement_satisfied(
                        requirement,
                        runtime_version,
                    )
                )
                if (
                    not compatible
                    and runtime_version in _LEGACY_DEDICATED_SDK_RUNTIME_VERSIONS
                    and line == "langbot-plugin==0.6.1"
                    and execution_mode == "dedicated"
                ):
                    identity = (
                        getattr(artifact, "plugin_author", None),
                        getattr(artifact, "plugin_name", None),
                        getattr(artifact, "plugin_version", None),
                    )
                    compatible = (
                        all(isinstance(part, str) for part in identity)
                        and _LEGACY_DEDICATED_SDK_061.get(identity)  # type: ignore[arg-type]
                        == getattr(artifact, "digest", None)
                    )
                if not compatible:
                    raise DependencyEnvironmentPreparationError(
                        "Plugin requires "
                        f"{requirement}, but the Runtime provides "
                        f"langbot-plugin=={runtime_version}"
                    )
                # The worker must always import the Runtime-owned SDK. Installing
                # another SDK into the plugin dependency tree can shadow newer
                # Runtime APIs, especially in editable development environments.
                continue

            requirements.append(str(requirement))
            if len(requirements) > _MAX_REQUIREMENT_COUNT:
                raise DependencyEnvironmentPreparationError(
                    "Plugin requirements.txt contains too many requirements"
                )
        return tuple(requirements), requirements_digest

    @staticmethod
    def _validate_installed_requirements(
        site_packages_path: pathlib.Path,
        requirements: Sequence[str],
    ) -> None:
        distributions: dict[str, list[importlib.metadata.Distribution]] = {}
        for distribution in importlib.metadata.distributions(
            path=[str(site_packages_path)]
        ):
            name = distribution.metadata.get("Name")
            if name:
                distributions.setdefault(canonicalize_name(name), []).append(
                    distribution
                )

        unsatisfied: list[str] = []
        for value in requirements:
            requirement = Requirement(value)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            matches = distributions.get(canonicalize_name(requirement.name), [])
            if requirement.url:
                if not matches:
                    unsatisfied.append(value)
                continue
            if not any(
                not requirement.specifier
                or distribution.version in requirement.specifier
                for distribution in matches
            ):
                unsatisfied.append(value)
        if unsatisfied:
            raise DependencyEnvironmentPreparationError(
                "Prepared dependency environment has "
                f"{len(unsatisfied)} unsatisfied requirement(s)"
            )

    @staticmethod
    def _iter_bounded_tree(
        root_path: pathlib.Path,
    ) -> Iterator[tuple[pathlib.Path, int]]:
        entries = 0
        total_bytes = 0
        for path in root_path.rglob("*"):
            entries += 1
            if entries > _MAX_ENVIRONMENT_ENTRIES:
                raise DependencyEnvironmentPreparationError(
                    "Prepared dependency environment contains too many entries"
                )
            metadata = path.lstat()
            mode = metadata.st_mode
            if stat.S_ISREG(mode):
                total_bytes += metadata.st_size
                if total_bytes > _MAX_ENVIRONMENT_TOTAL_BYTES:
                    raise DependencyEnvironmentPreparationError(
                        "Prepared dependency environment exceeds the total size limit"
                    )
            yield path, mode

    @classmethod
    def _validate_tree_entries(cls, root_path: pathlib.Path) -> None:
        for _, mode in cls._iter_bounded_tree(root_path):
            if stat.S_ISLNK(mode):
                raise DependencyEnvironmentPreparationError(
                    "Prepared dependency environment contains a symbolic link"
                )
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise DependencyEnvironmentPreparationError(
                    "Prepared dependency environment contains a special file"
                )

    @classmethod
    def _make_tree_read_only(cls, root_path: pathlib.Path) -> None:
        for path, raw_mode in cls._iter_bounded_tree(root_path):
            mode = stat.S_IMODE(raw_mode)
            if stat.S_ISDIR(raw_mode):
                path.chmod((mode & ~0o222) | 0o555)
            else:
                path.chmod((mode & ~0o222) | 0o444)
        root_path.chmod(0o555)

    @staticmethod
    def _write_marker(path: pathlib.Path, metadata: dict[str, object]) -> None:
        with path.open("w", encoding="utf-8") as marker:
            json.dump(metadata, marker, sort_keys=True, separators=(",", ":"))
            marker.write("\n")
            marker.flush()
            os.fsync(marker.fileno())
        path.chmod(0o444)

    @staticmethod
    def _fsync_directory(path: pathlib.Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError:
            return
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _environment_digest(
        artifact_digest: str,
        requirements_digest: str,
        runtime_fingerprint: str,
    ) -> str:
        payload = {
            "artifact_digest": artifact_digest,
            "requirements_digest": requirements_digest,
            "runtime_fingerprint": runtime_fingerprint,
            "schema_version": _ENVIRONMENT_SCHEMA_VERSION,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _metadata(
        *,
        digest: str,
        artifact_digest: str,
        requirements_digest: str,
        runtime_fingerprint: str,
    ) -> dict[str, object]:
        return {
            "artifact_digest": artifact_digest,
            "digest": digest,
            "requirements_digest": requirements_digest,
            "runtime_fingerprint": runtime_fingerprint,
            "schema_version": _ENVIRONMENT_SCHEMA_VERSION,
        }
