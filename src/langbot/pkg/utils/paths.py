"""Utility functions for finding package resources and runtime data roots."""

import os
from pathlib import Path


_is_source_install = None
_source_root = None


def _find_source_root() -> Path | None:
    """Locate the LangBot repository root when running from source."""
    global _source_root

    if _source_root is not None:
        return _source_root

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / 'pyproject.toml').exists() and (parent / 'main.py').exists():
            _source_root = parent
            return parent

    _source_root = None
    return None


def _check_if_source_install() -> bool:
    """
    Check if we're running from the LangBot source tree.
    Cached to avoid repeated filesystem scans.
    """
    global _is_source_install

    if _is_source_install is not None:
        return _is_source_install

    _is_source_install = _find_source_root() is not None
    return _is_source_install


def get_data_root() -> str:
    """
    Get the runtime data root.

    Priority:
    1. LANGBOT_DATA_ROOT environment override
    2. Source checkout root /data when running from source
    3. Current working directory /data for installed-package usage
    """
    env_root = os.environ.get('LANGBOT_DATA_ROOT', '').strip()
    if env_root:
        return str(Path(env_root).expanduser().resolve())

    source_root = _find_source_root()
    if source_root is not None:
        return str((source_root / 'data').resolve())

    return str((Path.cwd() / 'data').resolve())


def get_data_path(*parts: str) -> str:
    """Join path segments under the resolved data root."""
    data_root = Path(get_data_root())
    if not parts:
        return str(data_root)
    return str((data_root.joinpath(*parts)).resolve())


def get_frontend_path() -> str:
    """
    Get the path to the frontend build files.

    Returns the path to web/dist directory (Vite build output), handling both:
    - Development mode: running from source directory
    - Package mode: installed via pip/uvx
    - Legacy mode: web/out (Next.js, for backward compatibility)
    """
    # Check both dist (Vite) and out (legacy Next.js) paths
    for dirname in ('dist', 'out'):
        web_dir = f'web/{dirname}'

        # First, check if we're running from source directory
        if _check_if_source_install() and os.path.exists(web_dir):
            return web_dir

        # Second, check current directory
        if os.path.exists(web_dir):
            return web_dir

        # Third, find it relative to the package installation
        pkg_dir = Path(__file__).parent.parent.parent
        frontend_path = pkg_dir / 'web' / dirname
        if frontend_path.exists():
            return str(frontend_path)

    # Return the default path (will be checked by caller)
    return 'web/dist'


def get_resource_path(resource: str) -> str:
    """
    Get the path to a resource file.

    Args:
        resource: Relative path to resource (e.g., 'templates/config.yaml')

    Returns:
        Absolute path to the resource
    """
    # First, check if resource exists in current directory (source install)
    source_root = _find_source_root()
    if source_root is not None:
        source_resource = source_root / resource
        if source_resource.exists():
            return str(source_resource)

    # Second, check current directory anyway
    if os.path.exists(resource):
        return resource

    # Third, find it relative to package directory
    # Get the directory where this file is located
    # paths.py is in pkg/utils/, so parent.parent goes up to pkg/, then parent again goes up to the package root
    pkg_dir = Path(__file__).parent.parent.parent
    resource_path = pkg_dir / resource
    if resource_path.exists():
        return str(resource_path)

    # Return the original path
    return resource
