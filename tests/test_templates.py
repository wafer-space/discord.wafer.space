"""Tests for Jinja2 template rendering."""
import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def test_templates_directory_exists():
    """Test that templates directory exists"""
    templates_dir = Path("templates")
    assert templates_dir.exists(), "templates/ directory should exist"
    assert templates_dir.is_dir(), "templates/ should be a directory"


def test_site_index_template_exists():
    """Test that site_index.html.j2 exists"""
    template_path = Path("templates/site_index.html.j2")
    assert template_path.exists(), "site_index.html.j2 should exist"


def test_server_index_template_exists():
    """Test that server_index.html.j2 exists"""
    template_path = Path("templates/server_index.html.j2")
    assert template_path.exists(), "server_index.html.j2 should exist"


def test_channel_index_template_exists():
    """Test that channel_index.html.j2 exists"""
    template_path = Path("templates/channel_index.html.j2")
    assert template_path.exists(), "channel_index.html.j2 should exist"


def test_css_file_exists():
    """Test that style.css exists"""
    css_path = Path("public/assets/style.css")
    assert css_path.exists(), "style.css should exist"


def test_site_index_template_renders():
    """Test that site_index template can be rendered"""
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('site_index.html.j2')

    # Render with minimal data
    html = template.render(
        site={
            'title': 'Test Site',
            'description': 'Test Description'
        },
        servers=[
            {
                'name': 'test-server',
                'display_name': 'Test Server',
                'channel_count': 5,
                'last_updated': '2025-01-15 14:00 UTC'
            }
        ],
        last_updated='2025-01-15 14:00 UTC'
    )

    # Verify basic structure
    assert '<!DOCTYPE html>' in html
    assert 'Test Site' in html
    assert 'Test Description' in html
    assert 'Test Server' in html


def test_server_index_template_renders():
    """Test that server_index template can be rendered"""
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('server_index.html.j2')

    html = template.render(
        site={'title': 'Test Site'},
        server={
            'name': 'test-server',
            'display_name': 'Test Server'
        },
        channels=[
            {
                'name': 'general',
                'message_count': 100,
                'archive_count': 3,
                'archives': [
                    {'date': '2025-01', 'message_count': 50},
                    {'date': '2024-12', 'message_count': 30}
                ]
            }
        ]
    )

    assert '<!DOCTYPE html>' in html
    assert 'Test Server' in html
    assert '#general' in html


def test_channel_index_template_renders():
    """Test that channel_index template can be rendered"""
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('channel_index.html.j2')

    html = template.render(
        site={'title': 'Test Site'},
        server={
            'name': 'test-server',
            'display_name': 'Test Server'
        },
        channel={'name': 'general'},
        archives_by_year={
            '2025': [
                {'date': '2025-01', 'message_count': 100}
            ],
            '2024': [
                {'date': '2024-12', 'message_count': 150}
            ]
        }
    )

    assert '<!DOCTYPE html>' in html
    assert '#general' in html
    assert '2025' in html
    assert '2024' in html


def test_css_contains_discord_theme():
    """Test that CSS contains Discord-themed colors"""
    css_path = Path("public/assets/style.css")
    css_content = css_path.read_text()

    # Check for Discord dark theme colors
    assert '--bg-primary' in css_content or 'background' in css_content
    assert '--text-primary' in css_content or 'color' in css_content
    assert '--accent' in css_content or '#7289da' in css_content.lower()


def test_templates_use_css_link():
    """Test that templates link to style.css"""
    for template_name in ['site_index.html.j2', 'server_index.html.j2', 'channel_index.html.j2']:
        template_path = Path(f"templates/{template_name}")
        content = template_path.read_text()
        assert '/assets/style.css' in content, f"{template_name} should link to style.css"
