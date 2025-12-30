"""GitHub synchronization service for encrypted clipboard backup"""

import json
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
from github import Github, GithubException
from loguru import logger


class GitHubSyncService:
    """Manages GitHub synchronization for clipboard data"""

    def __init__(self, token: Optional[str] = None, repository: Optional[str] = None):
        """
        Initialize GitHub sync service

        Args:
            token: GitHub personal access token
            repository: Repository name (format: username/repo)
        """
        self.token = token
        self.repository_name = repository
        self.github = None
        self.repo = None
        self.enabled = False

        if token and repository:
            self.connect()

    def connect(self) -> bool:
        """
        Connect to GitHub

        Returns:
            True if successful
        """
        try:
            if not self.token:
                logger.warning("No GitHub token provided")
                return False

            self.github = Github(self.token)

            # Verify token by getting user
            user = self.github.get_user()
            logger.info(f"Connected to GitHub as: {user.login}")

            # Get or create repository
            if self.repository_name:
                self.repo = self._get_or_create_repo()
                if self.repo:
                    self.enabled = True
                    logger.info(f"Connected to repository: {self.repository_name}")
                    return True

            return False

        except GithubException as e:
            logger.error(f"GitHub connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during GitHub connection: {e}")
            return False

    def _get_or_create_repo(self):
        """
        Get existing repository or create new one

        Returns:
            Repository object or None
        """
        try:
            # Try to get existing repo
            repo = self.github.get_repo(self.repository_name)
            logger.info(f"Found existing repository: {self.repository_name}")
            return repo

        except GithubException as e:
            logger.debug(f"Repository not found with full name, trying to create: {e}")
            # Repository doesn't exist, try to create it
            try:
                user = self.github.get_user()
                repo_name = self.repository_name.split('/')[-1]

                # Check if repo exists under user account
                try:
                    repo = self.github.get_repo(f"{user.login}/{repo_name}")
                    logger.info(f"Found existing repository: {user.login}/{repo_name}")
                    return repo
                except GithubException:
                    # Really doesn't exist, create it
                    repo = user.create_repo(
                        name=repo_name,
                        private=True,
                        description="Encrypted ClipboardHistory backup",
                        auto_init=True
                    )
                    logger.info(f"Created new repository: {repo_name}")
                    return repo

            except GithubException as e:
                logger.error(f"Failed to create repository: {e}")
                # If creation failed due to already exists, try to get it one more time
                if "already exists" in str(e).lower():
                    try:
                        user = self.github.get_user()
                        repo_name = self.repository_name.split('/')[-1]
                        repo = self.github.get_repo(f"{user.login}/{repo_name}")
                        logger.info(f"Found existing repository after creation failed: {user.login}/{repo_name}")
                        return repo
                    except:
                        pass
                return None

    def upload_backup(self, data: Dict[str, Any], filename: Optional[str] = None) -> bool:
        """
        Upload encrypted backup to GitHub

        Args:
            data: Data to upload (should be encrypted)
            filename: Optional filename (defaults to timestamp)

        Returns:
            True if successful
        """
        if not self.enabled or not self.repo:
            logger.warning("GitHub sync not enabled")
            return False

        try:
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"clipboard_backup_{timestamp}.json"

            # Ensure data is in backups folder
            filepath = f"backups/{filename}"

            # Convert data to JSON
            content = json.dumps(data, indent=2)

            # Check if file exists
            try:
                existing_file = self.repo.get_contents(filepath)
                # Update existing file
                self.repo.update_file(
                    path=filepath,
                    message=f"Update clipboard backup: {filename}",
                    content=content,
                    sha=existing_file.sha
                )
                logger.info(f"Updated backup file: {filepath}")

            except GithubException:
                # Create new file
                self.repo.create_file(
                    path=filepath,
                    message=f"Add clipboard backup: {filename}",
                    content=content
                )
                logger.info(f"Created new backup file: {filepath}")

            return True

        except Exception as e:
            logger.error(f"Failed to upload backup: {e}")
            return False

    def download_backup(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Download backup from GitHub

        Args:
            filename: Name of backup file

        Returns:
            Backup data or None
        """
        if not self.enabled or not self.repo:
            logger.warning("GitHub sync not enabled")
            return None

        try:
            filepath = f"backups/{filename}"
            file_content = self.repo.get_contents(filepath)

            # Decode content
            content = base64.b64decode(file_content.content).decode('utf-8')
            data = json.loads(content)

            logger.info(f"Downloaded backup: {filepath}")
            return data

        except Exception as e:
            logger.error(f"Failed to download backup: {e}")
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backups

        Returns:
            List of backup metadata
        """
        if not self.enabled or not self.repo:
            logger.warning("GitHub sync not enabled")
            return []

        try:
            backups = []

            try:
                contents = self.repo.get_contents("backups")

                for file in contents:
                    if file.name.endswith('.json'):
                        backups.append({
                            'filename': file.name,
                            'path': file.path,
                            'size': file.size,
                            'sha': file.sha,
                            'last_modified': file.last_modified
                        })

            except GithubException:
                # Backups folder doesn't exist yet
                logger.info("No backups folder found")

            return sorted(backups, key=lambda x: x['filename'], reverse=True)

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def delete_backup(self, filename: str) -> bool:
        """
        Delete backup from GitHub

        Args:
            filename: Name of backup file

        Returns:
            True if successful
        """
        if not self.enabled or not self.repo:
            logger.warning("GitHub sync not enabled")
            return False

        try:
            filepath = f"backups/{filename}"
            file_content = self.repo.get_contents(filepath)

            self.repo.delete_file(
                path=filepath,
                message=f"Delete backup: {filename}",
                sha=file_content.sha
            )

            logger.info(f"Deleted backup: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def sync_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Sync application settings to GitHub

        Args:
            settings: Settings dictionary

        Returns:
            True if successful
        """
        if not self.enabled or not self.repo:
            return False

        try:
            filepath = "settings.json"
            content = json.dumps(settings, indent=2)

            try:
                # Update existing settings
                existing_file = self.repo.get_contents(filepath)
                self.repo.update_file(
                    path=filepath,
                    message="Update application settings",
                    content=content,
                    sha=existing_file.sha
                )

            except GithubException:
                # Create new settings file
                self.repo.create_file(
                    path=filepath,
                    message="Add application settings",
                    content=content
                )

            logger.info("Settings synced to GitHub")
            return True

        except Exception as e:
            logger.error(f"Failed to sync settings: {e}")
            return False

    def get_settings(self) -> Optional[Dict[str, Any]]:
        """
        Get settings from GitHub

        Returns:
            Settings dictionary or None
        """
        if not self.enabled or not self.repo:
            return None

        try:
            file_content = self.repo.get_contents("settings.json")
            content = base64.b64decode(file_content.content).decode('utf-8')
            settings = json.loads(content)

            logger.info("Settings retrieved from GitHub")
            return settings

        except GithubException:
            logger.info("No settings file found on GitHub")
            return None
        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test GitHub connection

        Returns:
            True if connection is working
        """
        try:
            if not self.github:
                return False

            # Try to get user info
            user = self.github.get_user()
            return user is not None

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_storage_usage(self) -> Dict[str, Any]:
        """
        Get storage usage information

        Returns:
            Storage usage stats
        """
        if not self.enabled or not self.repo:
            return {}

        try:
            backups = self.list_backups()
            total_size = sum(b['size'] for b in backups)

            return {
                'backup_count': len(backups),
                'total_size': total_size,
                'repository': self.repository_name
            }

        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {}