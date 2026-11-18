import importlib
import importlib.util
import os
import pkgutil
import sys
import typing


def import_modules_in_pkg(pkg: typing.Any) -> None:
    """
    导入一个包内的所有模块
    Args:
        pkg: 要导入的包对象
    """
    if hasattr(pkg, "__path__"):
        for module_info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            if not module_info.ispkg:
                importlib.import_module(module_info.name)
        return

    pkg_path = os.path.dirname(pkg.__file__)
    import_dir(pkg_path)


def import_modules_in_pkgs(pkgs: typing.List) -> None:
    for pkg in pkgs:
        import_modules_in_pkg(pkg)


def import_dot_style_dir(dot_sep_path: str):
    pkg = importlib.import_module(dot_sep_path)
    return import_modules_in_pkg(pkg)


def import_dir(path: str):
    abs_path = os.path.abspath(path)
    for file in os.listdir(path):
        if file.endswith(".py") and file != "__init__.py":
            full_path = os.path.abspath(os.path.join(abs_path, file))
            module_path = full_path[:-3]
            for root in sorted(sys.path, key=len, reverse=True):
                if not root:
                    root = os.getcwd()
                abs_root = os.path.abspath(root)
                try:
                    rel_path = os.path.relpath(module_path, abs_root)
                except ValueError:
                    continue
                if rel_path.startswith(".."):
                    continue
                importlib.import_module(rel_path.replace(os.sep, "."))
                break
