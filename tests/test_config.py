# tests/test_config.py
from scripts.config import load_config


def test_load_config_returns_dict():
    """Test that load_config returns a dictionary"""
    config = load_config("config.toml")
    assert isinstance(config, dict)

def test_load_config_has_required_sections():
    """Test that config has site, servers, export sections"""
    config = load_config("config.toml")
    assert "site" in config
    assert "servers" in config
    assert "export" in config
    assert "github" in config

def test_load_config_site_values():
    """Test that site section has required values"""
    config = load_config("config.toml")
    assert config["site"]["title"] == "wafer.space Discord Logs"
    assert "base_url" in config["site"]

def test_load_config_export_formats():
    """Test that export formats are parsed correctly"""
    config = load_config("config.toml")
    assert "html" in config["export"]["formats"]
    assert "txt" in config["export"]["formats"]
    assert "json" in config["export"]["formats"]
    assert "csv" in config["export"]["formats"]

def test_load_config_forum_channels():
    """Test that forum_channels are loaded from config."""
    config = load_config()

    assert 'servers' in config
    for server_key, server_config in config['servers'].items():
        # Should have forum_channels list
        assert 'forum_channels' in server_config
        assert isinstance(server_config['forum_channels'], list)


def test_load_config_forum_channels_values():
    """Test specific forum channel values."""
    config = load_config()

    wafer_space = config['servers']['wafer-space']
    assert 'questions' in wafer_space['forum_channels']
    assert 'ideas' in wafer_space['forum_channels']
