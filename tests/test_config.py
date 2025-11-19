# tests/test_config.py
from scripts.config import load_config


def test_load_config_returns_dict() -> None:
    """Test that load_config returns a dictionary"""
    config = load_config("config.toml")
    assert isinstance(config, dict)


def test_load_config_has_required_sections() -> None:
    """Test that config has site, servers, export sections"""
    config = load_config("config.toml")
    assert "site" in config
    assert "servers" in config
    assert "export" in config
    assert "github" in config


def test_load_config_site_values() -> None:
    """Test that site section has required values"""
    config = load_config("config.toml")
    assert config["site"]["title"] == "wafer.space Discord Logs"
    assert "base_url" in config["site"]


def test_load_config_export_formats() -> None:
    """Test that export formats are parsed correctly"""
    config = load_config("config.toml")
    assert "html" in config["export"]["formats"]
    assert "txt" in config["export"]["formats"]
    assert "json" in config["export"]["formats"]
    assert "csv" in config["export"]["formats"]


def test_load_config_forum_channels() -> None:
    """Test that forum_channels key is optional (forums are auto-detected)."""
    config = load_config()

    assert "servers" in config
    for _, server_config in config["servers"].items():
        # forum_channels is now optional since forums are auto-detected
        # If present, it should be a list
        if "forum_channels" in server_config:
            assert isinstance(server_config["forum_channels"], list)


def test_load_config_forum_channels_values() -> None:
    """Test that servers can exist without manual forum channel configuration."""
    config = load_config()

    wafer_space = config["servers"]["wafer-space"]
    # Forum channels are now auto-detected, so this key is optional
    # The config should work without manual forum_channels specification
    assert "guild_id" in wafer_space
    assert "name" in wafer_space
