from __future__ import annotations

import importlib
import sys
import textwrap

from langbot_plugin.utils import importutil


def test_import_dot_style_dir_imports_python_modules_from_package(
    tmp_path, monkeypatch
):
    package = tmp_path / "samplepkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "alpha.py").write_text("VALUE = 42\n", encoding="utf-8")
    (package / "notes.txt").write_text("ignored", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    importutil.import_dot_style_dir("samplepkg")

    assert importlib.import_module("samplepkg.alpha").VALUE == 42


def test_import_modules_in_pkg_uses_package_file_location(tmp_path, monkeypatch):
    package = tmp_path / "anotherpkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "beta.py").write_text("FLAG = 'loaded'\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    pkg = importlib.import_module("anotherpkg")

    importutil.import_modules_in_pkg(pkg)

    assert sys.modules["anotherpkg.beta"].FLAG == "loaded"


def test_import_dir_skips_init_files(tmp_path, monkeypatch):
    package = tmp_path / "thirdpkg"
    package.mkdir()
    (package / "__init__.py").write_text("RAISED = False\n", encoding="utf-8")
    (package / "gamma.py").write_text(
        textwrap.dedent(
            """
            RESULT = "ok"
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    importutil.import_dir(str(package))

    assert importlib.import_module("thirdpkg.gamma").RESULT == "ok"
