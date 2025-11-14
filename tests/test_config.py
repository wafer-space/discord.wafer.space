# tests/test_config.py
import pytest
from pathlib import Path
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
