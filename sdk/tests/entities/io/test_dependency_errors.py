from __future__ import annotations

from langbot_plugin.entities.io.errors import (
    DependencyInstallError,
    DependencyVerificationError,
)


def test_dependency_install_error_carries_structured_fields():
    err = DependencyInstallError(
        failed=["foo>=1", "bar"],
        plugin="alice/demo",
        details={"foo>=1": "could not find version", "bar": "network error"},
    )

    assert err.failed == ["foo>=1", "bar"]
    assert err.plugin == "alice/demo"
    assert err.details["bar"] == "network error"
    # The plugin ref and count appear in the message for log/UI surfacing.
    msg = str(err)
    assert "alice/demo" in msg
    assert "2 dependencies" in msg
    assert "foo>=1" in msg


def test_dependency_install_error_without_plugin():
    err = DependencyInstallError(failed=["foo"])
    assert err.plugin is None
    assert err.details == {}
    assert "1 dependencies" in str(err)
    # No leading "Plugin " prefix when the plugin ref is unknown.
    assert not str(err).startswith("Plugin ")


def test_dependency_install_error_is_exception():
    assert isinstance(DependencyInstallError(failed=["x"]), Exception)


def test_dependency_verification_error_carries_missing_and_mismatch():
    err = DependencyVerificationError(
        missing=["ghost"],
        version_mismatch=["pkg>=9999"],
        plugin="bob/plugin",
    )

    assert err.missing == ["ghost"]
    assert err.version_mismatch == ["pkg>=9999"]
    assert err.plugin == "bob/plugin"
    msg = str(err)
    assert "bob/plugin" in msg
    assert "ghost" in msg
    assert "pkg>=9999" in msg


def test_dependency_verification_error_defaults_mismatch_to_empty():
    err = DependencyVerificationError(missing=["ghost"])
    assert err.version_mismatch == []
    assert err.plugin is None
    assert isinstance(err, Exception)
