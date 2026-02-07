"""Tests for ArchiveManager"""

import os
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.services.archive_manager import ArchiveManager


class TestArchiveManager:
    """Tests for ArchiveManager"""

    @pytest.fixture
    def archive_mgr(self, temp_dir):
        """Create ArchiveManager with temp directory"""
        with patch.dict(os.environ, {'APPDATA': str(temp_dir)}):
            mgr = ArchiveManager()
            return mgr

    def test_init_creates_directory(self, archive_mgr):
        assert os.path.isdir(archive_mgr.archive_dir)

    def test_archive_entries(self, archive_mgr):
        entries = [
            {'content': 'test1', 'content_hash': 'h1', 'timestamp': datetime.now().isoformat()},
            {'content': 'test2', 'content_hash': 'h2', 'timestamp': datetime.now().isoformat()},
        ]
        result = archive_mgr.archive_entries(entries)
        assert result is True

        # Verify archive file was created
        files = [f for f in os.listdir(archive_mgr.archive_dir) if f.startswith('archive_')]
        assert len(files) == 1

    def test_archive_empty_list(self, archive_mgr):
        result = archive_mgr.archive_entries([])
        assert result is True

    def test_get_archived_entries(self, archive_mgr):
        entries = [
            {'content': 'archived1', 'content_hash': 'h1'},
            {'content': 'archived2', 'content_hash': 'h2'},
        ]
        archive_mgr.archive_entries(entries)

        retrieved = archive_mgr.get_archived_entries(days=7)
        assert len(retrieved) == 2

    def test_search_archives(self, archive_mgr):
        entries = [
            {'content': 'apple pie recipe'},
            {'content': 'banana smoothie'},
            {'content': 'apple sauce'}
        ]
        archive_mgr.archive_entries(entries)

        results = archive_mgr.search_archives("apple")
        assert len(results) == 2

    def test_search_archives_case_insensitive(self, archive_mgr):
        entries = [{'content': 'Hello World'}]
        archive_mgr.archive_entries(entries)
        results = archive_mgr.search_archives("hello")
        assert len(results) == 1

    def test_restore_from_archive(self, archive_mgr):
        entries = [
            {'content': 'restore_me', 'content_hash': 'restore_hash'},
        ]
        archive_mgr.archive_entries(entries)

        result = archive_mgr.restore_from_archive('restore_hash')
        assert result is not None
        assert result['content'] == 'restore_me'

    def test_restore_nonexistent_hash(self, archive_mgr):
        result = archive_mgr.restore_from_archive('nonexistent')
        assert result is None

    def test_get_archive_stats(self, archive_mgr):
        entries = [{'content': 'stat_test', 'content_hash': 'h1'}]
        archive_mgr.archive_entries(entries)

        stats = archive_mgr.get_archive_stats()
        assert stats['total_archives'] == 1
        assert stats['total_entries'] == 1
        assert stats['total_size_bytes'] > 0

    def test_cleanup_old_archives(self, archive_mgr):
        # Create an old archive manually
        old_filename = "archive_20200101_120000.json"
        old_path = os.path.join(archive_mgr.archive_dir, old_filename)
        with open(old_path, 'w') as f:
            json.dump({'entries': [], 'entry_count': 0}, f)

        # Set file modification time to past
        old_time = (datetime.now() - timedelta(days=30)).timestamp()
        os.utime(old_path, (old_time, old_time))

        deleted = archive_mgr.cleanup_old_archives()
        assert deleted >= 1
        assert not os.path.exists(old_path)
