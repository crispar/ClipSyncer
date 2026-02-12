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

### Entry Point
- `main_improved.py` - Main entry point (used by PyInstaller), contains `ClipboardHistoryApp` orchestrator class

### Core Components (`src/core/`)
- `exceptions.py` - Custom exception hierarchy: `ClipSyncerError` > `EncryptionError`, `DecryptionError`, `SyncError`, `StorageError`, `ConfigurationError`
- `interfaces.py` - ABC interfaces: `EncryptionStrategy`, `SyncBackend`, `StorageBackend` (Dependency Inversion Principle)
- `clipboard/` - `ClipboardMonitor` (polls clipboard), `ClipboardHistory` (in-memory storage with deduplication via content hash)
- `encryption/` - `EncryptionManager` (AES-256-GCM, implements `EncryptionStrategy`), `KeyManager` (Windows Credential Manager + PBKDF2 for sync password)
- `storage/` - `DatabaseManager` (SQLite via SQLAlchemy), `ClipboardRepository` (implements `StorageBackend`, data access layer via `repository_improved.py`)

### Services (`src/services/`)
- `component_factory.py` - `ComponentFactory`: Creates and wires all application components (extracted from God Class)
- `sync_coordinator.py` - `SyncCoordinator`: Manages all sync operations (push, pull, merge, initial sync)
- `sync/github_sync.py` - `GitHubSyncService` (implements `SyncBackend`): GitHub API integration, supports github.com and GitHub Enterprise
- `auto_sync_service.py` - `AutoSyncService`: Real-time push (5s debounce, 30s min interval) + periodic pull (60s)
- `archive_manager.py` - `ArchiveManager`: Archives overflow entries, uses `SyncBackend` public API (not internal repo object)
- `cleanup/` - `CleanupService`, `DuplicateRemover`, `OldDataCleaner`, `DatabaseOptimizer`

### UI (`src/ui/`)
- `tray/` - System tray icon using Qt-based Fluent Design (`tray_icon_fluent.py`)
- `history/` - `ModernHistoryViewer` (QMainWindow with qfluentwidgets)
- `dialogs/` - `GitHubSettingsDialog`, `AppSettingsDialog`, `WelcomeDialog`, `RestoreDialog`

### Configuration
- User config: `%APPDATA%/ClipboardHistory/settings.yaml`
- GitHub config: `%APPDATA%/ClipboardHistory/github_settings.yaml` (separate file)
- `ConfigManager` loads both files and merges them

## Key Design Patterns

### OOAD Architecture
- **Dependency Inversion**: Core classes depend on ABC interfaces (`EncryptionStrategy`, `SyncBackend`, `StorageBackend`), not concrete implementations
- **Single Responsibility**: `ComponentFactory` handles initialization, `SyncCoordinator` handles sync logic, `ClipboardHistoryApp` orchestrates UI and services
- **Custom Exceptions**: Typed exception hierarchy (`ClipSyncerError` base) with specific subtypes for encryption, sync, storage, and configuration errors
- **Encapsulation**: `GitHubSyncService` uses private fields (`_token`, `_repo`, `_github`) with property accessors; `EncryptionManager` uses `_key` with read-only property

### GitHub as Primary Storage
When GitHub sync is enabled, GitHub becomes the primary storage and local SQLite is cache-only. On startup, `SyncCoordinator.initial_sync()` clears local cache and pulls from GitHub.

### Encryption Flow
1. User sets sync password in settings dialog
2. `KeyManager.set_sync_password()` derives key using PBKDF2-HMAC-SHA256 (600k iterations, fixed salt)
3. Same password on different devices produces same encryption key
4. Content encrypted with `EncryptionManager.encrypt()` before GitHub upload
5. Wrong key decryption raises `DecryptionError` with clear message

### Sync Architecture
- `backups/clipboard_sync.json` - Single encrypted file containing all current entries (overwrites on each push)
- Bidirectional sync via `SyncCoordinator.pull_and_merge()`: pulls merge remote-only entries to local, then pushes local-only entries to remote
- Archives created by `ArchiveManager` for entries older than 7 days, stored in `archives/`

### Qt Thread Safety
- `QtSignalBridge` class with pyqtSignals for cross-thread communication
- Background operations (sync, cleanup) run in daemon threads
- UI updates must go through signal/slot mechanism

## Important Files

| File | Purpose |
|------|---------|
| `ClipSyncer.spec` | PyInstaller configuration with hidden imports for qfluentwidgets, PyQt6, keyring |
| `src/core/exceptions.py` | Custom exception hierarchy (ClipSyncerError, EncryptionError, etc.) |
| `src/core/interfaces.py` | ABC interfaces for DIP (EncryptionStrategy, SyncBackend, StorageBackend) |
| `src/services/component_factory.py` | Creates and wires all application components |
| `src/services/sync_coordinator.py` | Manages sync operations (push, pull, merge) |
| `src/utils/config_manager.py` | Loads settings.yaml + github_settings.yaml |
| `src/services/sync/github_sync.py` | `upload_backup()`, `download_backup()`, `push_latest()`, `pull_latest()` - supports Enterprise via `enterprise_url` |
| `src/services/auto_sync_service.py` | Real-time push (5s debounce, 30s min interval) + periodic pull (60s default) |

## Common Issues

- **GitHub sync not working**: Check that `github_settings.yaml` has `enabled: true` and repository is in `username/repo` format (not full URL)
- **qfluentwidgets import errors in exe**: Spec file uses `collect_data_files('qfluentwidgets')` to selectively collect required assets
- **Encryption mismatch between devices**: Must use same sync password on all devices
- **DecryptionError "wrong encryption key"**: User entered different sync password than what was used to encrypt
