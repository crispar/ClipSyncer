"""Tests for GitHubSyncService"""

import json
import hashlib
from unittest.mock import MagicMock, patch
import pytest

from src.services.sync.github_sync import GitHubSyncService


@pytest.fixture
def mock_github():
    """Create a mock GitHub instance"""
    with patch('src.services.sync.github_sync.Github') as MockGithub:
        mock_instance = MockGithub.return_value
        mock_user = MagicMock()
        mock_user.login = "testuser"
        mock_instance.get_user.return_value = mock_user

        mock_repo = MagicMock()
        # _get_or_create_repo calls self.github.get_repo(), not user.get_repo()
        mock_instance.get_repo.return_value = mock_repo

        yield {
            'github_class': MockGithub,
            'instance': mock_instance,
            'user': mock_user,
            'repo': mock_repo
        }


@pytest.fixture
def sync_service(mock_github):
    """GitHubSyncService with mocked GitHub"""
    service = GitHubSyncService(
        token="test_token",
        repository="testuser/testrepo"
    )
    return service


class TestGitHubSyncInit:
    """Tests for GitHubSyncService initialization"""

    def test_init_with_valid_params(self, mock_github):
        service = GitHubSyncService(
            token="token",
            repository="user/repo"
        )
        assert service.enabled is True
        assert service._repo is not None

    def test_init_missing_token(self, mock_github):
        service = GitHubSyncService(token="", repository="user/repo")
        assert service.enabled is False

    def test_init_missing_repo(self, mock_github):
        service = GitHubSyncService(token="token", repository="")
        assert service.enabled is False


class TestUploadBackup:
    """Tests for upload_backup with content hash check"""

    def test_upload_skips_unchanged_content(self, sync_service, mock_github):
        """Should skip upload when content hasn't changed"""
        data = {"entries": [{"content": "test"}]}
        content = json.dumps(data, indent=2)

        mock_file = MagicMock()
        mock_file.decoded_content = content.encode('utf-8')
        mock_file.sha = "abc123"
        mock_github['repo'].get_contents.return_value = mock_file

        result = sync_service.upload_backup(data)
        assert result is True
        # update_file should NOT be called since content is unchanged
        mock_github['repo'].update_file.assert_not_called()

    def test_upload_updates_changed_content(self, sync_service, mock_github):
        """Should upload when content has changed"""
        data = {"entries": [{"content": "new"}]}

        old_content = json.dumps({"entries": [{"content": "old"}]}, indent=2)
        mock_file = MagicMock()
        mock_file.decoded_content = old_content.encode('utf-8')
        mock_file.sha = "abc123"
        mock_github['repo'].get_contents.return_value = mock_file

        result = sync_service.upload_backup(data)
        assert result is True
        mock_github['repo'].update_file.assert_called_once()

    def test_upload_creates_new_file(self, sync_service, mock_github):
        """Should create file when it doesn't exist"""
        from github import GithubException

        mock_github['repo'].get_contents.side_effect = GithubException(
            404, {"message": "Not Found"}, {}
        )

        data = {"entries": []}
        result = sync_service.upload_backup(data)
        assert result is True
        mock_github['repo'].create_file.assert_called_once()

    def test_upload_disabled_service(self, mock_github):
        """Should return False when service is disabled"""
        service = GitHubSyncService(token="", repository="")
        result = service.upload_backup({"data": "test"})
        assert result is False


class TestDownloadBackup:
    """Tests for download_backup"""

    def test_download_success(self, sync_service, mock_github):
        """Should download and parse backup file"""
        data = {"entries": [{"content": "test"}]}
        content = json.dumps(data)

        mock_file = MagicMock()
        mock_file.decoded_content = content.encode('utf-8')
        mock_file.size = len(content)
        mock_file.encoding = "base64"
        mock_github['repo'].get_contents.return_value = mock_file

        result = sync_service.download_backup()
        assert result == data

    def test_download_file_not_found(self, sync_service, mock_github):
        """Should return None when file doesn't exist"""
        from github import GithubException
        mock_github['repo'].get_contents.side_effect = GithubException(
            404, {"message": "Not Found"}, {}
        )

        result = sync_service.download_backup()
        assert result is None

    def test_download_disabled_service(self, mock_github):
        """Should return None when service is disabled"""
        service = GitHubSyncService(token="", repository="")
        result = service.download_backup()
        assert result is None


class TestContentHashComparison:
    """Tests for the content hash comparison logic used in upload_backup"""

    def test_identical_json_produces_same_hash(self):
        """Verify that identical JSON content produces the same hash"""
        data = {"entries": [{"content": "test", "hash": "abc"}]}
        content1 = json.dumps(data, indent=2)
        content2 = json.dumps(data, indent=2)
        hash1 = hashlib.sha256(content1.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(content2.encode('utf-8')).hexdigest()
        assert hash1 == hash2

    def test_different_json_produces_different_hash(self):
        """Verify that different JSON content produces different hashes"""
        data1 = {"entries": [{"content": "old"}]}
        data2 = {"entries": [{"content": "new"}]}
        content1 = json.dumps(data1, indent=2)
        content2 = json.dumps(data2, indent=2)
        hash1 = hashlib.sha256(content1.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(content2.encode('utf-8')).hexdigest()
        assert hash1 != hash2
