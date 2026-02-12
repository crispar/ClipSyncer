"""Archive Manager for handling overflow clipboard entries"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger


class ArchiveManager:
    """Manages archived clipboard entries when main history exceeds limit"""

    ARCHIVE_FOLDER = "archives"
    ARCHIVE_RETENTION_DAYS = 7

    def __init__(self, github_sync_service=None):
        """
        Initialize archive manager

        Args:
            github_sync_service: Optional GitHubSyncService for cloud archives
        """
        self.github_sync = github_sync_service
        self.archive_dir = self._get_archive_directory()

        # Create archive directory if it doesn't exist
        os.makedirs(self.archive_dir, exist_ok=True)

        # Clean old archives on initialization
        self.cleanup_old_archives()

    def _get_archive_directory(self) -> str:
        """Get local archive directory path"""
        config_dir = os.path.join(
            os.environ.get('APPDATA', '.'),
            'ClipboardHistory',
            self.ARCHIVE_FOLDER
        )
        return config_dir

    def archive_entries(self, entries: List[Dict[str, Any]]) -> bool:
        """
        Archive a list of clipboard entries

        Args:
            entries: List of entries to archive

        Returns:
            True if successful
        """
        if not entries:
            return True

        try:
            # Generate archive filename with current date
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_filename = f"archive_{timestamp}.json"

            # Prepare archive data
            archive_data = {
                'archived_at': datetime.now().isoformat(),
                'entry_count': len(entries),
                'entries': entries,
                'expires_at': (datetime.now() + timedelta(days=self.ARCHIVE_RETENTION_DAYS)).isoformat()
            }

            # Save to local archive
            local_path = os.path.join(self.archive_dir, archive_filename)
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Archived {len(entries)} entries to {archive_filename}")

            # If GitHub sync is enabled, upload to cloud
            if self.github_sync and self.github_sync.enabled:
                self._upload_archive_to_github(archive_filename, archive_data)

            return True

        except Exception as e:
            logger.error(f"Failed to archive entries: {e}")
            return False

    def _upload_archive_to_github(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        Upload archive to GitHub

        Args:
            filename: Archive filename
            data: Archive data

        Returns:
            True if successful
        """
        try:
            filepath = f"archives/{filename}"
            content = json.dumps(data, indent=2)

            success = self.github_sync.upload_file(
                filepath=filepath,
                content=content,
                message=f"Archive: {filename}"
            )

            if success:
                logger.debug(f"Uploaded archive to GitHub: {filename}")
            return success

        except Exception as e:
            logger.error(f"Failed to upload archive to GitHub: {e}")
            return False

    def cleanup_old_archives(self) -> int:
        """
        Remove archives older than retention period

        Returns:
            Number of archives deleted
        """
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.ARCHIVE_RETENTION_DAYS)

        try:
            # Clean local archives
            for filename in os.listdir(self.archive_dir):
                if filename.startswith('archive_') and filename.endswith('.json'):
                    file_path = os.path.join(self.archive_dir, filename)

                    # Check file modification time
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted expired archive: {filename}")

            # Clean GitHub archives if enabled
            if self.github_sync and self.github_sync.enabled:
                deleted_count += self._cleanup_github_archives(cutoff_date)

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired archives")

        except Exception as e:
            logger.error(f"Error during archive cleanup: {e}")

        return deleted_count

    def _cleanup_github_archives(self, cutoff_date: datetime) -> int:
        """
        Clean up old archives on GitHub

        Args:
            cutoff_date: Delete archives older than this date

        Returns:
            Number of archives deleted
        """
        deleted_count = 0

        try:
            files = self.github_sync.list_folder("archives")
            if not files:
                return 0

            for file_info in files:
                name = file_info['name']
                if name.startswith('archive_') and name.endswith('.json'):
                    try:
                        date_part = name[8:16]  # Extract YYYYMMDD
                        file_date = datetime.strptime(date_part, '%Y%m%d')

                        if file_date < cutoff_date:
                            success = self.github_sync.delete_file(
                                filepath=file_info['path'],
                                message=f"Delete expired archive: {name}"
                            )
                            if success:
                                deleted_count += 1
                                logger.debug(f"Deleted expired GitHub archive: {name}")
                    except Exception as e:
                        logger.debug(f"Could not parse date from {name}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning GitHub archives: {e}")

        return deleted_count

    def get_archived_entries(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Retrieve archived entries from the past N days

        Args:
            days: Number of days to look back

        Returns:
            List of archived entries
        """
        all_entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Read local archives
            for filename in os.listdir(self.archive_dir):
                if filename.startswith('archive_') and filename.endswith('.json'):
                    file_path = os.path.join(self.archive_dir, filename)

                    # Check file time
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time >= cutoff_date:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            all_entries.extend(data.get('entries', []))

        except Exception as e:
            logger.error(f"Error retrieving archived entries: {e}")

        return all_entries

    def search_archives(self, query: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Search for entries in archives

        Args:
            query: Search query
            days: Number of days to search back

        Returns:
            List of matching entries
        """
        matching_entries = []
        query_lower = query.lower()

        entries = self.get_archived_entries(days)
        for entry in entries:
            content = entry.get('content', '')
            if isinstance(content, str) and query_lower in content.lower():
                matching_entries.append(entry)

        return matching_entries

    def restore_from_archive(self, entry_hash: str) -> Optional[Dict[str, Any]]:
        """
        Restore a specific entry from archives

        Args:
            entry_hash: Content hash of the entry to restore

        Returns:
            The entry if found, None otherwise
        """
        try:
            for filename in os.listdir(self.archive_dir):
                if filename.startswith('archive_') and filename.endswith('.json'):
                    file_path = os.path.join(self.archive_dir, filename)

                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for entry in data.get('entries', []):
                            if entry.get('content_hash') == entry_hash:
                                logger.info(f"Restored entry from archive: {filename}")
                                return entry
        except Exception as e:
            logger.error(f"Error restoring from archive: {e}")

        return None

    def get_archive_stats(self) -> Dict[str, Any]:
        """
        Get statistics about archived data

        Returns:
            Dictionary with archive statistics
        """
        stats = {
            'total_archives': 0,
            'total_entries': 0,
            'oldest_archive': None,
            'newest_archive': None,
            'total_size_bytes': 0
        }

        try:
            archives = []
            for filename in os.listdir(self.archive_dir):
                if filename.startswith('archive_') and filename.endswith('.json'):
                    file_path = os.path.join(self.archive_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_size = os.path.getsize(file_path)

                    archives.append((file_time, filename, file_size))
                    stats['total_archives'] += 1
                    stats['total_size_bytes'] += file_size

                    # Count entries
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            stats['total_entries'] += data.get('entry_count', 0)
                    except Exception:
                        pass

            if archives:
                archives.sort(key=lambda x: x[0])
                stats['oldest_archive'] = archives[0][1]
                stats['newest_archive'] = archives[-1][1]

        except Exception as e:
            logger.error(f"Error getting archive stats: {e}")

        return stats