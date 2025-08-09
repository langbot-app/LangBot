import importlib
import importlib.util
import os
import typing


def import_modules_in_pkg(pkg: typing.Any) -> None:
    """
    导入一个包内的所有模块
    Args:
        pkg: 要导入的包对象
    """
    pkg_path = os.path.dirname(pkg.__file__)
    import_dir(pkg_path)


def import_modules_in_pkgs(pkgs: typing.List) -> None:
    for pkg in pkgs:
        import_modules_in_pkg(pkg)


def import_dot_style_dir(dot_sep_path: str):
    sec = dot_sep_path.split('.')

    return import_dir(os.path.join(*sec))


def import_dir(path: str):
    for file in os.listdir(path):
        if file.endswith('.py') and file != '__init__.py':
            full_path = os.path.join(path, file)
            rel_path = full_path.replace(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '')
            rel_path = rel_path[1:]
            rel_path = rel_path.replace('/', '.')[:-3]
            rel_path = rel_path.replace('\\', '.')
            importlib.import_module(rel_path)


if __name__ == '__main__':
    from pkg.platform import types

    import_modules_in_pkg(types)
