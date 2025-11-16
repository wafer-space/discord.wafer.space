# scripts/config.py
"""Configuration management for discord-wafer-space."""

from pathlib import Path
from typing import Any, cast

import toml


def load_config(config_path: str = "config.toml") -> dict[str, Any]:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config.toml file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        toml.TomlDecodeError: If config file is invalid
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = toml.load(f)

    return cast("dict[str, Any]", config)
