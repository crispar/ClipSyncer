# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClipSyncer is a Windows clipboard history manager with encrypted GitHub sync. It uses PyQt6 with qfluentwidgets for a modern Fluent Design UI.

## Build Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run in development
python main_improved.py

# Build executable (uses ClipSyncer.spec)
python build.py

# Or manually with PyInstaller
pyinstaller ClipSyncer.spec --clean --noconfirm

# Linting and formatting
black .                    # Code formatting
flake8                     # Linting
mypy .                     # Type checking

# Testing
pytest                     # Run all tests
pytest tests/test_file.py  # Run single test file
pytest -v                  # Verbose output
```

Output: `dist/ClipSyncer.exe`

Logs location: `%APPDATA%/ClipboardHistory/logs/` (script) or `./logs/` (exe)

## Architecture

### Entry Points
- `main_improved.py` - Main entry point (used by PyInstaller), contains `ClipboardHistoryApp` class
- `main.py` - Legacy entry point (similar structure but fewer features)

### Core Components (`src/core/`)
- `clipboard/` - `ClipboardMonitor` (polls clipboard), `ClipboardHistory` (in-memory storage with deduplication via content hash)
- `encryption/` - `EncryptionManager` (AES-256-GCM), `KeyManager` (Windows Credential Manager + PBKDF2 for sync password)
- `storage/` - `DatabaseManager` (SQLite via SQLAlchemy), `ClipboardRepository` (data access layer)

### Services (`src/services/`)
- `sync/github_sync.py` - `GitHubSyncService`: GitHub API integration, supports both github.com and GitHub Enterprise
- `auto_sync_service.py` - `AutoSyncService`: Real-time push (5s debounce, 30s min interval) + periodic pull (60s)
- `archive_manager.py` - `ArchiveManager`: Moves old entries to `backups/` folder after 7 days
- `cleanup/` - `CleanupService`, `DuplicateRemover`, `OldDataCleaner`, `DatabaseOptimizer`

### UI (`src/ui/`)
- `tray/` - System tray icon using `pystray`
- `history/` - `ModernHistoryViewer` (QMainWindow with qfluentwidgets)
- `dialogs/` - `GitHubSettingsDialog`, `WelcomeDialog` (first-run setup)

### Configuration
- User config: `%APPDATA%/ClipboardHistory/settings.yaml`
- GitHub config: `%APPDATA%/ClipboardHistory/github_settings.yaml` (separate file)
- `ConfigManager` loads both files and merges them

## Key Design Patterns

### GitHub as Primary Storage
When GitHub sync is enabled, GitHub becomes the primary storage and local SQLite is cache-only. On startup, the app clears local cache and pulls from GitHub.

### Encryption Flow
1. User sets sync password in settings dialog
2. `KeyManager.set_sync_password()` derives key using PBKDF2-HMAC-SHA256 (600k iterations, fixed salt)
3. Same password on different devices produces same encryption key
4. Content encrypted with `EncryptionManager.encrypt()` before GitHub upload

### Sync Architecture
- `backups/clipboard_sync.json` - Single encrypted file containing all current entries (overwrites on each push)
- Bidirectional sync: pulls merge remote-only entries to local, then pushes local-only entries to remote
- Archives created by `ArchiveManager` for entries older than 7 days, stored in `backups/archives/`

### Qt Thread Safety
- `QtSignalBridge` class with pyqtSignals for cross-thread communication
- Background operations (sync, cleanup) run in daemon threads
- UI updates must go through signal/slot mechanism

## Important Files

| File | Purpose |
|------|---------|
| `ClipSyncer.spec` | PyInstaller configuration with hidden imports for qfluentwidgets, PyQt6, keyring |
| `src/utils/config_manager.py` | Loads settings.yaml + github_settings.yaml |
| `src/services/sync/github_sync.py` | `upload_backup()`, `download_backup()`, `push_latest()`, `pull_latest()` - supports Enterprise via `enterprise_url` |
| `src/services/auto_sync_service.py` | Real-time push (5s debounce, 30s min interval) + periodic pull (60s default) |

## Common Issues

- **GitHub sync not working**: Check that `github_settings.yaml` has `enabled: true` and repository is in `username/repo` format (not full URL)
- **qfluentwidgets import errors in exe**: Ensure `collect_all('qfluentwidgets')` is in spec file
- **Encryption mismatch between devices**: Must use same sync password on all devices
