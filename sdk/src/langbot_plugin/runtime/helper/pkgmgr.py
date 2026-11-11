import asyncio
import concurrent.futures
import importlib.metadata
import importlib.util
import logging
import json
import os
import re
import subprocess
import sys
import pathlib
import venv

from packaging.requirements import Requirement
from pip._internal import main as pipmain


PYPI_INDEX_URL_ENV = "LANGBOT_PLUGIN_PYPI_INDEX_URL"
PYPI_TRUSTED_HOST_ENV = "LANGBOT_PLUGIN_PYPI_TRUSTED_HOST"
DEFAULT_PYPI_INDEX_URL = "https://pypi.org/simple"
logger = logging.getLogger(__name__)
PLUGIN_VENV_DIR = ".venv"
DEFAULT_INSTALL_TIMEOUT_SEC = 300.0
MAX_INSTALL_OUTPUT_BYTES = 1024 * 1024
_SUBPROCESS_READ_CHUNK_BYTES = 64 * 1024


async def _terminate_subprocess(proc: asyncio.subprocess.Process) -> None:
    """Terminate and reap a subprocess without leaving cancellation orphans."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=2)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()


async def _read_bounded_stream(
    stream: asyncio.StreamReader | None,
    *,
    max_bytes: int = MAX_INSTALL_OUTPUT_BYTES,
) -> tuple[bytes, int]:
    """Drain a subprocess pipe while retaining at most ``max_bytes``."""

    if stream is None:
        return b"", 0
    retained = bytearray()
    total = 0
    while True:
        chunk = await stream.read(_SUBPROCESS_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        remaining = max_bytes - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
    return bytes(retained), total


def _render_captured_output(data: bytes, total: int) -> str:
    text = data.decode("utf-8", errors="replace")
    discarded = total - len(data)
    if discarded > 0:
        text += (
            f"\n... [dependency installer output clipped at "
            f"{MAX_INSTALL_OUTPUT_BYTES} bytes, {discarded} bytes discarded]"
        )
    return text


async def _wait_with_bounded_output(
    proc: asyncio.subprocess.Process,
    *,
    timeout_sec: float,
) -> tuple[bytes, int, bytes, int, bool]:
    """Wait for a subprocess and drain both pipes without unbounded buffering."""

    stdout_task = asyncio.create_task(_read_bounded_stream(proc.stdout))
    stderr_task = asyncio.create_task(_read_bounded_stream(proc.stderr))
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        timed_out = True
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
    except asyncio.CancelledError:
        await _terminate_subprocess(proc)
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        raise

    stdout, stdout_total = await stdout_task
    stderr, stderr_total = await stderr_task
    return stdout, stdout_total, stderr, stderr_total, timed_out


logger = logging.getLogger(__name__)


def get_pip_index_args() -> list[str]:
    """Build pip index args from environment. Defaults to official PyPI."""
    index_url = os.getenv(PYPI_INDEX_URL_ENV, DEFAULT_PYPI_INDEX_URL).strip()
    args: list[str] = []

    if index_url:
        args.extend(["-i", index_url])

    trusted_hosts = os.getenv(PYPI_TRUSTED_HOST_ENV, "")
    for host in [item.strip() for item in trusted_hosts.split(",") if item.strip()]:
        args.extend(["--trusted-host", host])

    return args


def install(package):
    pipmain(["install", package, *get_pip_index_args()])


def install_upgrade(package):
    pipmain(
        [
            "install",
            "--upgrade",
            package,
            *get_pip_index_args(),
        ]
    )


def run_pip(params: list):
    pipmain(params)


def install_requirements(file, extra_params: list = []):
    pipmain(
        [
            "install",
            "-r",
            file,
            *get_pip_index_args(),
        ]
        + extra_params
    )


def parse_requirements(file: str) -> list[str]:
    """Parse requirements.txt and return list of package specs."""
    deps = []
    with open(file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                deps.append(line)
    return deps


def install_single(
    package: str, extra_params: list | None = None
) -> tuple[int, int, str]:
    """Install a package and return (returncode, downloaded_bytes, output)."""
    if extra_params is None:
        extra_params = []

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package,
        *get_pip_index_args(),
    ] + extra_params

    returncode, output = _run_subprocess_bounded_sync(
        cmd,
        timeout_sec=DEFAULT_INSTALL_TIMEOUT_SEC,
    )
    downloaded_bytes = _parse_downloaded_bytes(output)
    return returncode, downloaded_bytes, output


def _read_bounded_sync(
    stream,
    *,
    max_bytes: int = MAX_INSTALL_OUTPUT_BYTES,
) -> tuple[bytes, int]:
    retained = bytearray()
    total = 0
    while True:
        chunk = stream.read(_SUBPROCESS_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        remaining = max_bytes - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
    return bytes(retained), total


def _run_subprocess_bounded_sync(
    cmd: list[str],
    *,
    timeout_sec: float,
) -> tuple[int, str]:
    """Synchronous compatibility path with bounded stdout/stderr retention."""

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    timed_out = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        stdout_future = executor.submit(_read_bounded_sync, proc.stdout)
        stderr_future = executor.submit(_read_bounded_sync, proc.stderr)
        try:
            proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        stdout, stdout_total = stdout_future.result()
        stderr, stderr_total = stderr_future.result()

    output = _render_captured_output(stdout, stdout_total)
    output += "\n" + _render_captured_output(stderr, stderr_total)
    if timed_out:
        output += f"\nDependency installation timed out after {timeout_sec:.0f}s"
        return 124, output
    return proc.returncode, output


async def install_single_async(
    package: str,
    extra_params: list | None = None,
    *,
    python_executable: str | None = None,
    timeout_sec: float = DEFAULT_INSTALL_TIMEOUT_SEC,
) -> tuple[int, int, str]:
    """Install a package via async subprocess without blocking the event loop."""
    if extra_params is None:
        extra_params = []

    cmd = [
        python_executable or sys.executable,
        "-m",
        "pip",
        "install",
        package,
        *get_pip_index_args(),
    ] + extra_params

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    (
        stdout_bytes,
        stdout_total,
        stderr_bytes,
        stderr_total,
        timed_out,
    ) = await _wait_with_bounded_output(proc, timeout_sec=timeout_sec)
    stdout_text = _render_captured_output(stdout_bytes, stdout_total)
    stderr_text = _render_captured_output(stderr_bytes, stderr_total)
    if timed_out:
        stderr_text += f"\nDependency installation timed out after {timeout_sec:.0f}s"
        return (
            124,
            0,
            stdout_text + "\n" + stderr_text,
        )
    output = stdout_text + "\n" + stderr_text
    downloaded_bytes = _parse_downloaded_bytes(output)
    return proc.returncode, downloaded_bytes, output


def _parse_downloaded_bytes(output: str) -> int:
    """Parse pip output to extract total downloaded bytes."""
    total = 0
    for line in output.splitlines():
        m = re.search(r"Downloading\s+\S+\s+\(([0-9.]+)\s*(kB|MB|GB|bytes?)\)", line)
        if m:
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit == "kb":
                total += int(val * 1024)
            elif unit == "mb":
                total += int(val * 1024 * 1024)
            elif unit == "gb":
                total += int(val * 1024 * 1024 * 1024)
            else:
                total += int(val)
    return total


_dist_to_packages: dict[str, set[str]] | None = None


def _is_distribution_installed(pkg_name: str) -> bool:
    """Check whether a pip distribution is installed via its metadata.

    This is the authoritative check, regardless of whether the pip
    package name matches the actual Python module name.
    """
    candidates = {pkg_name, pkg_name.replace("-", "_"), pkg_name.replace("_", "-")}
    for name in candidates:
        try:
            importlib.metadata.distribution(name)
            return True
        except importlib.metadata.PackageNotFoundError:
            continue
    return False


def _resolve_import_names(pkg_name: str) -> set[str]:
    """Resolve top-level Python import names for a pip distribution.

    Many pip package names differ from their importable module name.
    E.g. yiri-mirai -> mirai, PyYAML -> yaml, Pillow -> PIL.
    Uses importlib.metadata.packages_distributions() reverse mapping.
    """
    global _dist_to_packages

    if _dist_to_packages is None:
        _dist_to_packages = {}
        try:
            for (
                top_pkg,
                dist_names,
            ) in importlib.metadata.packages_distributions().items():
                for dist_name in dist_names:
                    key = dist_name.lower().replace("_", "-")
                    _dist_to_packages.setdefault(key, set()).add(top_pkg)
        except Exception as exc:
            logger.debug(
                "Failed to load package distribution metadata: %s", exc, exc_info=True
            )

    key = pkg_name.lower().replace("_", "-")
    names = _dist_to_packages.get(key, set()).copy()
    names.add(pkg_name.replace("-", "_"))
    return names


def _check_dependency_installed(dep_spec: str) -> bool:
    """Check whether a dependency requirement is fully satisfied.

    Returns True only when:
    1. Environment markers do not apply → treat as satisfied (skip)
    2. Distribution is installed AND version satisfies the specifier
    3. Package is importable (fallback for name-mismatch cases,
       e.g. yiri-mirai → mirai, PyYAML → yaml)

    Returns False when the installed version does not meet the specifier
    or the package is not installed at all.
    """
    try:
        req = Requirement(dep_spec)
    except Exception:
        # parse_requirements() already filters comments, empty lines, and
        # option lines (-r / --index-url).  If Requirement() still fails, the
        # input is genuinely malformed and no heuristic name extraction will
        # be reliable.  Return False so pip gets a chance to install it.
        return False

    if req.marker and not req.marker.evaluate():
        return True

    pkg_name = req.name

    if _is_distribution_installed(pkg_name):
        if req.url:
            # URL requirements (e.g. ``foo @ https://...``) cannot be
            # reliably verified from Python — the installed distribution
            # may have come from a different source or version.  Reading
            # pip's internal direct_url.json (PEP 610) is fragile and
            # couples us to pip implementation details.  Returning True
            # would risk silently keeping a mismatched version.
            #
            # Instead, return False so pip decides.  If the URL points to
            # an already-satisfied version, pip will output "Requirement
            # already satisfied" and exit without downloading — the
            # overhead is a single subprocess spawn.
            return False
        if not req.specifier:
            return True
        try:
            installed_version = importlib.metadata.version(pkg_name)
            return installed_version in req.specifier
        except importlib.metadata.PackageNotFoundError:
            return False

    for import_name in _resolve_import_names(pkg_name):
        if importlib.util.find_spec(import_name) is not None:
            return True

    return False


async def verify_dependencies(deps: list[str]) -> list[str]:
    """Verify installed dependencies are actually importable.

    Returns:
        List of dependency specs that failed verification.
    """
    missing, _ = classify_unsatisfied_dependencies(deps)
    return missing


def classify_unsatisfied_dependencies(
    deps: list[str],
) -> tuple[list[str], list[str]]:
    """Split dependency specs into (missing, version_mismatch).

    A spec is reported as ``version_mismatch`` when its distribution IS
    installed but the installed version does not satisfy the requested
    specifier; otherwise, if it is not satisfied at all, it is ``missing``.
    Specs that are satisfied (including skipped environment markers and
    URL requirements whose distribution exists) are omitted from both lists.

    Returns:
        (missing, version_mismatch) — two disjoint lists of requirement specs.
    """
    missing: list[str] = []
    version_mismatch: list[str] = []
    for dep in deps:
        if _check_dependency_installed(dep):
            continue

        try:
            req = Requirement(dep)
        except Exception:
            # Genuinely malformed spec — pip should have decided. Treat as
            # missing so the caller surfaces it rather than silently passing.
            missing.append(dep)
            continue

        # Environment marker excludes this dep from the current env → satisfied.
        if req.marker and not req.marker.evaluate():
            continue

        # URL requirement: _check_dependency_installed always defers to pip and
        # returns False. After pip has run, the presence of the distribution is
        # sufficient verification.
        if req.url:
            if _is_distribution_installed(req.name):
                continue
            missing.append(dep)
            continue

        # Distribution present but specifier not met → version mismatch.
        if req.specifier and _is_distribution_installed(req.name):
            version_mismatch.append(dep)
            continue

        missing.append(dep)
    return missing, version_mismatch


async def install_with_retry(
    package: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    extra_params: list | None = None,
    python_executable: str | None = None,
    timeout_sec: float = DEFAULT_INSTALL_TIMEOUT_SEC,
) -> tuple[int, int, str]:
    """Install a package with retry on failure.

    Args:
        package: Package name to install.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay between retries in seconds.
        extra_params: Additional pip parameters.

    Returns:
        (returncode, downloaded_bytes, error_message)
    """
    last_error = ""
    for attempt in range(max_retries):
        returncode, downloaded_bytes, output = await install_single_async(
            package,
            extra_params,
            python_executable=python_executable,
            timeout_sec=timeout_sec,
        )
        if returncode == 0:
            return returncode, downloaded_bytes, ""

        last_error = (
            f"Attempt {attempt + 1}/{max_retries} failed with code {returncode}"
        )
        if output.strip():
            last_error += f"\n{output.strip()}"

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    return returncode, 0, last_error


def get_plugin_python(plugin_path: str) -> str:
    """Return the isolated interpreter for a plugin when it exists."""
    candidate = (
        pathlib.Path(plugin_path)
        / PLUGIN_VENV_DIR
        / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if candidate.is_file():
        return str(candidate.resolve())
    return str(pathlib.Path(sys.executable).resolve())


def get_plugin_site_packages(plugin_path: str) -> str | None:
    """Return the plugin-local dependency directory when it exists."""
    root = pathlib.Path(plugin_path) / PLUGIN_VENV_DIR
    candidate = (
        root / "Lib" / "site-packages"
        if sys.platform == "win32"
        else root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    if candidate.is_dir():
        return str(candidate.resolve())
    return None


async def ensure_plugin_environment(plugin_path: str) -> str:
    """Create a plugin-local environment that can still import the SDK.

    System site packages expose the runtime's SDK without reinstalling it, while
    dependencies installed into the venv shadow only this plugin's imports.
    """
    root = pathlib.Path(plugin_path) / PLUGIN_VENV_DIR
    candidate = root / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    if candidate.is_file():
        return str(candidate.resolve())

    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(root)
    if not candidate.is_file():
        raise RuntimeError(f"Plugin virtual environment was not created at {root}")
    return str(candidate.resolve())


async def install_requirements_isolated(
    plugin_path: str,
    *,
    timeout_sec: float = DEFAULT_INSTALL_TIMEOUT_SEC,
) -> tuple[int, str]:
    """Install a plugin's requirements without blocking the runtime loop."""
    requirements_file = pathlib.Path(plugin_path) / "requirements.txt"
    if not requirements_file.is_file():
        return 0, ""

    python_path = await ensure_plugin_environment(plugin_path)
    proc = await asyncio.create_subprocess_exec(
        python_path,
        "-m",
        "pip",
        "install",
        "-r",
        str(requirements_file),
        *get_pip_index_args(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    (
        stdout,
        stdout_total,
        stderr,
        stderr_total,
        timed_out,
    ) = await _wait_with_bounded_output(proc, timeout_sec=timeout_sec)
    output = _render_captured_output(stdout, stdout_total)
    output += _render_captured_output(stderr, stderr_total)
    if timed_out:
        return 124, output + f"\nTimed out after {timeout_sec:.0f}s"
    return proc.returncode or 0, output


async def classify_requirements_in_environment(
    python_executable: str,
    deps: list[str],
    *,
    timeout_sec: float = 30.0,
) -> tuple[list[str], list[str]]:
    """Verify requirements against the interpreter that will run the plugin."""
    verifier = r"""
import importlib.metadata
import json
import sys
from packaging.requirements import Requirement

missing = []
version_mismatch = []
for spec in json.loads(sys.argv[1]):
    try:
        req = Requirement(spec)
    except Exception:
        missing.append(spec)
        continue
    if req.marker and not req.marker.evaluate():
        continue
    try:
        version = importlib.metadata.version(req.name)
    except importlib.metadata.PackageNotFoundError:
        missing.append(spec)
        continue
    if req.specifier and version not in req.specifier:
        version_mismatch.append(spec)
print(json.dumps([missing, version_mismatch]))
"""
    proc = await asyncio.create_subprocess_exec(
        python_executable,
        "-c",
        verifier,
        json.dumps(deps),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    (
        stdout,
        stdout_total,
        stderr,
        stderr_total,
        timed_out,
    ) = await _wait_with_bounded_output(proc, timeout_sec=timeout_sec)
    if timed_out:
        return list(deps), []
    if proc.returncode != 0:
        raise RuntimeError(
            "Dependency verification subprocess failed: "
            + _render_captured_output(stderr, stderr_total).strip()
        )
    if stdout_total > MAX_INSTALL_OUTPUT_BYTES:
        raise RuntimeError("Dependency verification output exceeded the runtime limit")
    result = json.loads(stdout.decode("utf-8"))
    return list(result[0]), list(result[1])


async def precheck_dependencies(requirements_file: str) -> dict:
    """Pre-check dependency status before installation.

    Returns:
        {
            'deps': list[str],
            'already_installed': list[str],
            'to_install': list[str],
            'conflicts': list[str],
        }
    """
    deps = parse_requirements(requirements_file)
    already_installed = []
    to_install = []

    for dep in deps:
        if _check_dependency_installed(dep):
            already_installed.append(dep)
        else:
            to_install.append(dep)

    return {
        "deps": deps,
        "already_installed": already_installed,
        "to_install": to_install,
        "conflicts": [],
    }
