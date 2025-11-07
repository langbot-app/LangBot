"""Utility functions for finding package resources"""
import os
import sys
from pathlib import Path


def get_frontend_path() -> str:
    """
    Get the path to the frontend build files.
    
    Returns the path to web/out directory, handling both:
    - Development mode: running from source directory
    - Package mode: installed via pip/uvx
    """
    # First, check if we're running from source directory
    # (main.py exists in current directory)
    if os.path.exists('main.py') and os.path.exists('web/out'):
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'LangBot/main.py' in content:
                return 'web/out'
    
    # Second, check if we're in a development/source directory
    # (current directory has web/out)
    if os.path.exists('web/out'):
        return 'web/out'
    
    # Third, try to find it relative to this file's location
    # This handles the case when installed as a package
    pkg_dir = Path(__file__).parent.parent.parent
    frontend_path = pkg_dir / 'web' / 'out'
    if frontend_path.exists():
        return str(frontend_path)
    
    # Fourth, check if it's in the package installation directory
    # Look for the web/out directory in the sys.path
    for path in sys.path:
        candidate = Path(path) / 'web' / 'out'
        if candidate.exists():
            return str(candidate)
    
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
    # First, check if resource exists in current directory
    if os.path.exists(resource):
        return resource
    
    # Second, try to find it relative to package directory
    pkg_dir = Path(__file__).parent.parent.parent
    resource_path = pkg_dir / resource
    if resource_path.exists():
        return str(resource_path)
    
    # Third, check in sys.path
    for path in sys.path:
        candidate = Path(path) / resource
        if candidate.exists():
            return str(candidate)
    
    # Return the original path
    return resource
