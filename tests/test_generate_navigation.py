# tests/test_generate_navigation.py
import pytest
import tempfile
from pathlib import Path
from scripts.generate_navigation import (
    scan_exports,
    count_messages_from_json,
    group_by_year,
    generate_site_index,
    generate_server_index,
    generate_channel_index
)

def test_scan_exports_finds_files():
    """Test that scan_exports finds exported files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake export structure
        public = Path(tmpdir) / "public"
        server_dir = public / "test-server" / "general"
        server_dir.mkdir(parents=True)

        (server_dir / "2025-01.html").touch()
        (server_dir / "2025-01.json").touch()
        (server_dir / "2025-01.txt").touch()

        exports = scan_exports(public)

        assert len(exports) > 0
        assert any(e['channel'] == 'general' for e in exports)

def test_scan_exports_skips_index_files():
    """Test that scan_exports skips index.html files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        public = Path(tmpdir) / "public"
        server_dir = public / "test-server" / "general"
        server_dir.mkdir(parents=True)

        (server_dir / "2025-01.html").touch()
        (server_dir / "index.html").touch()
        (public / "index.html").touch()

        exports = scan_exports(public)

        # Should only find 2025-01.html, not the index files
        assert len(exports) == 1
        assert exports[0]['date'] == '2025-01'

def test_scan_exports_multiple_channels():
    """Test scanning multiple channels and servers"""
    with tempfile.TemporaryDirectory() as tmpdir:
        public = Path(tmpdir) / "public"

        # Create multiple servers and channels
        (public / "server1" / "general" / "2025-01.html").parent.mkdir(parents=True)
        (public / "server1" / "general" / "2025-01.html").touch()
        (public / "server1" / "announcements" / "2025-01.html").parent.mkdir(parents=True)
        (public / "server1" / "announcements" / "2025-01.html").touch()
        (public / "server2" / "chat" / "2025-02.html").parent.mkdir(parents=True)
        (public / "server2" / "chat" / "2025-02.html").touch()

        exports = scan_exports(public)

        assert len(exports) == 3
        servers = {e['server'] for e in exports}
        channels = {e['channel'] for e in exports}
        assert 'server1' in servers
        assert 'server2' in servers
        assert 'general' in channels
        assert 'announcements' in channels
        assert 'chat' in channels

def test_count_messages_from_json():
    """Test counting messages from JSON file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Write sample JSON lines
        f.write('{"id": "1", "content": "Hello"}\n')
        f.write('{"id": "2", "content": "World"}\n')
        f.write('{"id": "3", "content": "Test"}\n')
        json_path = f.name

    count = count_messages_from_json(json_path)
    assert count == 3

    Path(json_path).unlink()

def test_count_messages_from_json_empty_lines():
    """Test counting messages ignores empty lines"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"id": "1", "content": "Hello"}\n')
        f.write('\n')
        f.write('{"id": "2", "content": "World"}\n')
        f.write('   \n')
        f.write('{"id": "3", "content": "Test"}\n')
        json_path = f.name

    count = count_messages_from_json(json_path)
    assert count == 3

    Path(json_path).unlink()

def test_count_messages_from_json_nonexistent():
    """Test counting messages from nonexistent file returns 0"""
    count = count_messages_from_json('/nonexistent/path/file.json')
    assert count == 0

def test_group_by_year():
    """Test grouping archives by year"""
    archives = [
        {'date': '2025-01', 'message_count': 100},
        {'date': '2025-02', 'message_count': 150},
        {'date': '2024-12', 'message_count': 200},
        {'date': '2024-11', 'message_count': 250},
    ]

    grouped = group_by_year(archives)

    assert '2025' in grouped
    assert '2024' in grouped
    assert len(grouped['2025']) == 2
    assert len(grouped['2024']) == 2

def test_group_by_year_sorted():
    """Test that archives within each year are sorted reverse chronologically"""
    archives = [
        {'date': '2025-01', 'message_count': 100},
        {'date': '2025-03', 'message_count': 150},
        {'date': '2025-02', 'message_count': 200},
    ]

    grouped = group_by_year(archives)

    # Should be sorted newest first: 2025-03, 2025-02, 2025-01
    assert grouped['2025'][0]['date'] == '2025-03'
    assert grouped['2025'][1]['date'] == '2025-02'
    assert grouped['2025'][2]['date'] == '2025-01'

def test_generate_site_index():
    """Test generating site index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "index.html"

        config = {
            'site': {
                'title': 'Test Discord Logs',
                'description': 'Test description'
            }
        }

        servers = [
            {
                'name': 'test-server',
                'display_name': 'Test Server',
                'channel_count': 5,
                'last_updated': '2025-01-15 14:00 UTC'
            }
        ]

        generate_site_index(config, servers, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert 'Test Discord Logs' in html
        assert 'Test Server' in html
        assert '5 channels' in html

def test_generate_server_index():
    """Test generating server index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "test-server" / "index.html"

        config = {
            'site': {
                'title': 'Test Discord Logs'
            }
        }

        server = {
            'name': 'test-server',
            'display_name': 'Test Server'
        }

        channels = [
            {
                'name': 'general',
                'message_count': 100,
                'archive_count': 3,
                'archives': []
            }
        ]

        generate_server_index(config, server, channels, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert 'Test Server' in html
        assert '#general' in html

def test_generate_channel_index():
    """Test generating channel index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "test-server" / "general" / "index.html"

        config = {
            'site': {
                'title': 'Test Discord Logs'
            }
        }

        server = {
            'name': 'test-server',
            'display_name': 'Test Server'
        }

        channel = {
            'name': 'general'
        }

        archives = [
            {'date': '2025-01', 'message_count': 100},
            {'date': '2025-02', 'message_count': 150},
        ]

        generate_channel_index(config, server, channel, archives, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert '#general' in html
        assert '2025-01' in html
        assert '2025-02' in html
