"""Utility functions for finding package resources"""

import os
from pathlib import Path


_is_source_install = None


def _check_if_source_install() -> bool:
    """
    Check if we're running from source directory or an installed package.
    Cached to avoid repeated file I/O.
    """
    global _is_source_install

    if _is_source_install is not None:
        return _is_source_install

    # Check if main.py exists in current directory with LangBot marker
    if os.path.exists('main.py'):
        try:
            with open('main.py', 'r', encoding='utf-8') as f:
                # Only read first 500 chars to check for marker
                content = f.read(500)
                if 'LangBot/main.py' in content:
                    _is_source_install = True
                    return True
        except (IOError, OSError, UnicodeDecodeError):
            # If we can't read the file, assume not a source install
            pass

    _is_source_install = False
    return False


def get_frontend_path() -> str:
    """
    Get the path to the frontend build files.

    Returns the path to web/out directory, handling both:
    - Development mode: running from source directory
    - Package mode: installed via pip/uvx
    """
    # First, check if we're running from source directory
    if _check_if_source_install() and os.path.exists('web/out'):
        return 'web/out'

    # Second, check current directory for web/out (in case user is in source dir)
    if os.path.exists('web/out'):
        return 'web/out'

    # Third, find it relative to the package installation
    # Get the directory where this file is located
    # paths.py is in pkg/utils/, so parent.parent goes up to pkg/, then parent again goes up to the package root
    pkg_dir = Path(__file__).parent.parent.parent
    frontend_path = pkg_dir / 'web' / 'out'
    if frontend_path.exists():
        return str(frontend_path)

    # Return the default path (will be checked by caller)
    return 'web/out'


def get_resource_path(resource: str) -> str:
    """
    Get the path to a resource file.

    Args:
        resource: Relative path to resource (e.g., 'templates/config.yaml')

    Returns:
        Absolute path to the resource
    """
    # First, check if resource exists in current directory (source install)
    if _check_if_source_install() and os.path.exists(resource):
        return resource

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
