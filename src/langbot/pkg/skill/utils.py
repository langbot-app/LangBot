"""Shared utilities for skill file parsing."""

import yaml


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content.

    Expects format:
        ---
        name: my-skill
        description: Does something
        ---
        # Actual instructions...

    Returns:
        Tuple of (metadata dict, remaining content)
    """
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    frontmatter_str = parts[1].strip()
    instructions = parts[2].strip()

    try:
        metadata = yaml.safe_load(frontmatter_str) or {}
    except yaml.YAMLError:
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    return metadata, instructions
