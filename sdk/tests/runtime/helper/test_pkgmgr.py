from __future__ import annotations

import asyncio
import pathlib

import pytest

from langbot_plugin.runtime.helper import pkgmgr


def test_get_pip_index_args_defaults_to_official_pypi(monkeypatch):
    monkeypatch.delenv(pkgmgr.PYPI_INDEX_URL_ENV, raising=False)
    monkeypatch.delenv(pkgmgr.PYPI_TRUSTED_HOST_ENV, raising=False)

    assert pkgmgr.get_pip_index_args() == ["-i", pkgmgr.DEFAULT_PYPI_INDEX_URL]


def test_get_pip_index_args_reads_custom_index_and_trusted_hosts(monkeypatch):
    monkeypatch.setenv(pkgmgr.PYPI_INDEX_URL_ENV, "https://mirror/simple")
    monkeypatch.setenv(pkgmgr.PYPI_TRUSTED_HOST_ENV, "mirror.local, cache.local ")

    assert pkgmgr.get_pip_index_args() == [
        "-i",
        "https://mirror/simple",
        "--trusted-host",
        "mirror.local",
        "--trusted-host",
        "cache.local",
    ]


def test_parse_requirements_ignores_comments_blank_lines_and_options(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "\n# comment\nrequests>=2\n-r base.txt\n--index-url https://mirror\npydantic\n",
        encoding="utf-8",
    )

    assert pkgmgr.parse_requirements(str(requirements)) == ["requests>=2", "pydantic"]


def test_parse_downloaded_bytes_supports_common_pip_units():
    output = "\n".join(
        [
            "Downloading a.whl (1.5 kB)",
            "Downloading b.whl (2 MB)",
            "Downloading c.whl (3 bytes)",
        ]
    )

    assert (
        pkgmgr._parse_downloaded_bytes(output) == int(1.5 * 1024) + 2 * 1024 * 1024 + 3
    )


def test_install_single_builds_pip_command_and_returns_parsed_download_size(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(pkgmgr, "get_pip_index_args", lambda: ["-i", "https://mirror"])
    monkeypatch.setattr(
        pkgmgr.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("bounded helper should be patched"),
    )
    monkeypatch.setattr(
        pkgmgr,
        "_run_subprocess_bounded_sync",
        lambda cmd, **kwargs: calls.append((cmd, kwargs))
        or (0, "Downloading pkg.whl (1 kB)"),
    )

    returncode, downloaded, output = pkgmgr.install_single("demo", ["--no-deps"])

    assert returncode == 0
    assert downloaded == 1024
    assert "Downloading pkg.whl" in output
    assert calls[0][0][-4:] == ["demo", "-i", "https://mirror", "--no-deps"]


def test_install_requirements_passes_extra_params_to_pip(monkeypatch):
    calls = []
    monkeypatch.setattr(pkgmgr, "get_pip_index_args", lambda: ["-i", "https://mirror"])
    monkeypatch.setattr(pkgmgr, "pipmain", lambda params: calls.append(params))

    pkgmgr.install_requirements("requirements.txt", ["--no-deps"])

    assert calls == [
        [
            "install",
            "-r",
            "requirements.txt",
            "-i",
            "https://mirror",
            "--no-deps",
        ]
    ]


def test_install_single_async_builds_pip_command_and_parses_output(monkeypatch):
    class Proc:
        returncode = 0

        def __init__(self):
            self.stdout = asyncio.StreamReader()
            self.stdout.feed_data(b"Downloading async.whl (2 kB)")
            self.stdout.feed_eof()
            self.stderr = asyncio.StreamReader()
            self.stderr.feed_eof()

        async def wait(self):
            return self.returncode

    calls = []

    async def fake_create_subprocess_exec(*cmd, stdout=None, stderr=None):
        calls.append((cmd, stdout, stderr))
        return Proc()

    monkeypatch.setattr(pkgmgr, "get_pip_index_args", lambda: [])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    returncode, downloaded, output = asyncio.run(pkgmgr.install_single_async("demo"))

    assert returncode == 0
    assert downloaded == 2048
    assert "Downloading async.whl" in output
    assert calls[0][0][-2:] == ("install", "demo")


class _BlockingProcess:
    def __init__(self):
        self.returncode = None
        self.wait_started = asyncio.Event()
        self._done = asyncio.Event()
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self._done.set()

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self._done.set()

    async def wait(self):
        self.wait_started.set()
        await self._done.wait()
        return self.returncode


@pytest.mark.asyncio
async def test_install_single_async_reaps_subprocess_when_cancelled(monkeypatch):
    process = _BlockingProcess()

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    task = asyncio.create_task(pkgmgr.install_single_async("demo"))
    await process.wait_started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.terminated
    assert not process.killed


@pytest.mark.asyncio
async def test_read_bounded_stream_discards_excess_bytes():
    stream = asyncio.StreamReader()
    stream.feed_data(b"abcdefghij")
    stream.feed_eof()

    retained, total = await pkgmgr._read_bounded_stream(stream, max_bytes=4)

    assert retained == b"abcd"
    assert total == 10


def test_get_plugin_python_returns_absolute_venv_interpreter(tmp_path):
    executable = (
        tmp_path
        / ".venv"
        / ("Scripts/python.exe" if pkgmgr.sys.platform == "win32" else "bin/python")
    )
    executable.parent.mkdir(parents=True)
    executable.touch()

    result = pkgmgr.get_plugin_python(str(tmp_path))

    assert pathlib.Path(result).is_absolute()
    assert pathlib.Path(result) == executable.resolve()


def test_get_plugin_site_packages_returns_existing_dependency_directory(tmp_path):
    site_packages = (
        tmp_path / ".venv" / "Lib" / "site-packages"
        if pkgmgr.sys.platform == "win32"
        else tmp_path
        / ".venv"
        / "lib"
        / f"python{pkgmgr.sys.version_info.major}.{pkgmgr.sys.version_info.minor}"
        / "site-packages"
    )
    site_packages.mkdir(parents=True)

    result = pkgmgr.get_plugin_site_packages(str(tmp_path))

    assert result == str(site_packages.resolve())


@pytest.mark.asyncio
async def test_ensure_plugin_environment_creates_missing_venv_for_symlinked_host_python(
    monkeypatch, tmp_path
):
    executable = (
        tmp_path
        / ".venv"
        / ("Scripts/python.exe" if pkgmgr.sys.platform == "win32" else "bin/python")
    )
    created_roots = []

    class FakeEnvBuilder:
        def __init__(self, *, with_pip, system_site_packages):
            assert with_pip is True
            assert system_site_packages is True

        def create(self, root):
            created_roots.append(pathlib.Path(root))
            executable.parent.mkdir(parents=True)
            executable.touch()

    monkeypatch.setattr(pkgmgr.venv, "EnvBuilder", FakeEnvBuilder)
    monkeypatch.setattr(pkgmgr.sys, "executable", "/host/.venv/bin/python")

    result = await pkgmgr.ensure_plugin_environment(str(tmp_path))

    assert created_roots == [tmp_path / ".venv"]
    assert pathlib.Path(result) == executable.resolve()


@pytest.mark.asyncio
async def test_install_requirements_reaps_subprocess_when_cancelled(
    monkeypatch, tmp_path
):
    (tmp_path / "requirements.txt").write_text("demo\n", encoding="utf-8")
    process = _BlockingProcess()

    async def fake_ensure_plugin_environment(plugin_path):
        return pkgmgr.sys.executable

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(
        pkgmgr, "ensure_plugin_environment", fake_ensure_plugin_environment
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    task = asyncio.create_task(pkgmgr.install_requirements_isolated(str(tmp_path)))
    await process.wait_started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.terminated
    assert not process.killed


# ---------------------------------------------------------------------------
# Dependency satisfaction checks (_check_dependency_installed)
#
# These anchor on packages that are guaranteed installed in the test/runtime
# environment (declared in pyproject): pytest, packaging, pydantic. PyYAML is
# the canonical pip-name != module-name case (distribution "PyYAML", import
# "yaml"). We avoid asserting on the *absence* of well-known names; instead we
# use a deliberately fabricated name for the not-installed path.
# ---------------------------------------------------------------------------

_DEFINITELY_ABSENT = "langbot-totally-absent-package-xyz"


def test_check_dependency_installed_plain_name_present():
    assert pkgmgr._check_dependency_installed("pytest") is True


def test_check_dependency_installed_absent_package():
    assert pkgmgr._check_dependency_installed(_DEFINITELY_ABSENT) is False


def test_check_dependency_installed_canonical_vs_underscore_dash():
    # Distribution lookup tries name, dash<->underscore variants. "pytest" is
    # single-token; use a multi-token absent name to ensure variants are tried
    # without false positives.
    assert pkgmgr._check_dependency_installed("langbot_totally_absent_xyz") is False


def test_check_dependency_installed_version_specifier_satisfied():
    import importlib.metadata as m

    ver = m.version("packaging")
    assert pkgmgr._check_dependency_installed(f"packaging>={ver}") is True
    assert pkgmgr._check_dependency_installed("packaging>=1.0") is True


def test_check_dependency_installed_version_specifier_violated():
    # An impossibly high lower bound must not be satisfied by the installed one.
    assert pkgmgr._check_dependency_installed("packaging>=9999.0") is False


def test_check_dependency_installed_exact_pin_mismatch():
    assert pkgmgr._check_dependency_installed("pytest==0.0.1") is False


def test_check_dependency_installed_name_module_mismatch_pyyaml():
    # Distribution name PyYAML, importable module name "yaml". The metadata
    # lookup must resolve it without relying on the import name.
    assert pkgmgr._check_dependency_installed("PyYAML") is True
    assert pkgmgr._check_dependency_installed("pyyaml") is True


def test_check_dependency_installed_skips_inapplicable_marker():
    # A marker that never matches the current interpreter → treated as satisfied.
    spec = f"{_DEFINITELY_ABSENT}; python_version < '2.0'"
    assert pkgmgr._check_dependency_installed(spec) is True


def test_check_dependency_installed_applicable_marker_still_checks():
    # Marker matches → the (absent) package is still evaluated and unsatisfied.
    spec = f"{_DEFINITELY_ABSENT}; python_version >= '3.0'"
    assert pkgmgr._check_dependency_installed(spec) is False


def test_check_dependency_installed_url_requirement_defers_to_pip():
    # URL requirements always return False so pip gets to decide, even when a
    # distribution of the same name happens to be installed.
    spec = "packaging @ https://example.invalid/packaging.whl"
    assert pkgmgr._check_dependency_installed(spec) is False


def test_check_dependency_installed_malformed_spec_returns_false():
    # Requirement() raises on this; helper must return False (let pip try).
    assert pkgmgr._check_dependency_installed(">>>not a spec<<<") is False


def test_check_dependency_installed_importable_fallback(monkeypatch):
    # Distribution metadata missing but the module is importable (name-mismatch
    # safety net). Force the metadata path to miss, keep the import path hot.
    monkeypatch.setattr(pkgmgr, "_is_distribution_installed", lambda name: False)
    monkeypatch.setattr(pkgmgr, "_resolve_import_names", lambda name: {"os"})
    assert pkgmgr._check_dependency_installed("anything-here") is True


def test_resolve_import_names_includes_underscore_variant():
    names = pkgmgr._resolve_import_names("PyYAML")
    # Reverse mapping should surface the real import module "yaml".
    assert "yaml" in names


def test_is_distribution_installed_variants():
    assert pkgmgr._is_distribution_installed("pytest") is True
    assert pkgmgr._is_distribution_installed(_DEFINITELY_ABSENT) is False


# ---------------------------------------------------------------------------
# precheck_dependencies
# ---------------------------------------------------------------------------


def test_precheck_dependencies_categorizes(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"pytest\npackaging>=1.0\n{_DEFINITELY_ABSENT}\n",
        encoding="utf-8",
    )

    result = asyncio.run(pkgmgr.precheck_dependencies(str(requirements)))

    assert result["deps"] == ["pytest", "packaging>=1.0", _DEFINITELY_ABSENT]
    assert "pytest" in result["already_installed"]
    assert "packaging>=1.0" in result["already_installed"]
    assert result["to_install"] == [_DEFINITELY_ABSENT]
    assert result["conflicts"] == []


def test_precheck_dependencies_all_installed(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest\npackaging\n", encoding="utf-8")

    result = asyncio.run(pkgmgr.precheck_dependencies(str(requirements)))

    assert result["to_install"] == []
    assert set(result["already_installed"]) == {"pytest", "packaging"}


# ---------------------------------------------------------------------------
# verify_dependencies / classify_unsatisfied_dependencies
# ---------------------------------------------------------------------------


def test_verify_dependencies_all_satisfied_returns_empty():
    assert asyncio.run(pkgmgr.verify_dependencies(["pytest", "packaging"])) == []


def test_verify_dependencies_reports_missing():
    missing = asyncio.run(pkgmgr.verify_dependencies([_DEFINITELY_ABSENT, "pytest"]))
    assert missing == [_DEFINITELY_ABSENT]


def test_classify_splits_missing_and_version_mismatch():
    deps = [
        "pytest",  # satisfied
        _DEFINITELY_ABSENT,  # missing (no distribution at all)
        "packaging>=9999.0",  # installed but version too low → mismatch
    ]
    missing, version_mismatch = pkgmgr.classify_unsatisfied_dependencies(deps)

    assert missing == [_DEFINITELY_ABSENT]
    assert version_mismatch == ["packaging>=9999.0"]


def test_classify_skips_inapplicable_marker():
    deps = [f"{_DEFINITELY_ABSENT}; python_version < '2.0'"]
    missing, version_mismatch = pkgmgr.classify_unsatisfied_dependencies(deps)
    assert missing == []
    assert version_mismatch == []


def test_classify_malformed_spec_is_missing():
    missing, version_mismatch = pkgmgr.classify_unsatisfied_dependencies(["@@bad@@"])
    assert missing == ["@@bad@@"]
    assert version_mismatch == []


def test_classify_url_requirement_satisfied_when_distribution_present(monkeypatch):
    # URL req whose distribution exists post-install → neither missing nor mismatch.
    monkeypatch.setattr(pkgmgr, "_is_distribution_installed", lambda name: True)
    spec = "packaging @ https://example.invalid/packaging.whl"
    missing, version_mismatch = pkgmgr.classify_unsatisfied_dependencies([spec])
    assert missing == []
    assert version_mismatch == []


def test_classify_url_requirement_missing_when_distribution_absent(monkeypatch):
    monkeypatch.setattr(pkgmgr, "_is_distribution_installed", lambda name: False)
    spec = "ghostpkg @ https://example.invalid/ghostpkg.whl"
    missing, version_mismatch = pkgmgr.classify_unsatisfied_dependencies([spec])
    assert missing == [spec]
    assert version_mismatch == []


# ---------------------------------------------------------------------------
# install_with_retry
# ---------------------------------------------------------------------------


def _patch_install_sequence(monkeypatch, results):
    """Patch install_single_async to yield the given (rc, bytes, output) tuples."""
    seq = list(results)
    calls = {"n": 0}

    async def fake_install(
        package,
        extra_params=None,
        *,
        python_executable=None,
        timeout_sec=pkgmgr.DEFAULT_INSTALL_TIMEOUT_SEC,
    ):
        calls["n"] += 1
        return seq.pop(0)

    monkeypatch.setattr(pkgmgr, "install_single_async", fake_install)
    return calls


def test_install_with_retry_succeeds_first_attempt(monkeypatch):
    calls = _patch_install_sequence(monkeypatch, [(0, 1024, "")])

    rc, downloaded, err = asyncio.run(
        pkgmgr.install_with_retry("demo", max_retries=3, retry_delay=0)
    )

    assert rc == 0
    assert downloaded == 1024
    assert err == ""
    assert calls["n"] == 1


def test_install_with_retry_recovers_after_transient_failure(monkeypatch):
    calls = _patch_install_sequence(
        monkeypatch,
        [
            (1, 0, "temporary network error"),
            (0, 2048, ""),
        ],
    )
    sleeps = []
    monkeypatch.setattr(pkgmgr.asyncio, "sleep", _record_async(sleeps))

    rc, downloaded, err = asyncio.run(
        pkgmgr.install_with_retry("demo", max_retries=3, retry_delay=0.01)
    )

    assert rc == 0
    assert downloaded == 2048
    assert err == ""
    assert calls["n"] == 2
    # One sleep between the failed attempt and the successful retry.
    assert sleeps == [0.01]


def test_install_with_retry_exhausts_and_returns_last_error(monkeypatch):
    calls = _patch_install_sequence(
        monkeypatch,
        [
            (1, 0, "err-1"),
            (1, 0, "err-2"),
            (2, 0, "fatal-3"),
        ],
    )
    sleeps = []
    monkeypatch.setattr(pkgmgr.asyncio, "sleep", _record_async(sleeps))

    rc, downloaded, err = asyncio.run(
        pkgmgr.install_with_retry("demo", max_retries=3, retry_delay=0.01)
    )

    assert rc == 2  # last returncode preserved
    assert downloaded == 0
    assert "Attempt 3/3" in err
    assert "fatal-3" in err  # pip stderr surfaced for debugging
    assert calls["n"] == 3
    # Sleeps only happen between attempts, not after the final one.
    assert sleeps == [0.01, 0.01]


def test_install_with_retry_no_sleep_after_final_attempt(monkeypatch):
    _patch_install_sequence(monkeypatch, [(1, 0, "x"), (1, 0, "y")])
    sleeps = []
    monkeypatch.setattr(pkgmgr.asyncio, "sleep", _record_async(sleeps))

    asyncio.run(pkgmgr.install_with_retry("demo", max_retries=2, retry_delay=0.5))

    # 2 attempts → exactly 1 inter-attempt sleep.
    assert sleeps == [0.5]


def _record_async(bucket):
    async def _sleep(delay):
        bucket.append(delay)

    return _sleep
