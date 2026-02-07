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
- `main_improved.py` - Sole entry point, contains `ClipboardHistoryApp` and `QtSignalBridge`

### Core Components (`src/core/`)
- `clipboard/` - `ClipboardMonitor` (polls via pyperclip), `ClipboardHistory` (in-memory storage with deduplication, `remove_entry()`, `import_entry()`)
- `encryption/` - `EncryptionManager` (AES-256-GCM), `KeyManager` (Windows Credential Manager + PBKDF2HMAC for sync password)
- `storage/` - `DatabaseManager` (SQLite via SQLAlchemy), `ClipboardRepository` (data access layer with `is_favorite()`, context-managed sessions)

### Services (`src/services/`)
- `sync/github_sync.py` - `GitHubSyncService`: GitHub API integration (github.com + GitHub Enterprise), large file handling (>1MB)
- `auto_sync_service.py` - `AutoSyncService`: Real-time push (5s debounce, 30s min interval) + periodic pull (60s)
- `archive_manager.py` - `ArchiveManager`: Moves overflow entries to local/GitHub archives with 7-day retention
- `cleanup/` - `CleanupService` (APScheduler), `DuplicateRemover`, `OldDataCleaner`, `DatabaseOptimizer`

### UI (`src/ui/`)
- `tray/` - `ModernTrayIcon` (QSystemTrayIcon with Windows 11 Fluent Design, exported as `TrayIcon`)
- `history/` - `ModernHistoryViewer` (QMainWindow with qfluentwidgets, exported as `HistoryViewer`)
- `dialogs/` - `GitHubSettingsDialog`, `WelcomeDialog`, `AppSettingsDialog`, `RestoreDialog`

### Configuration
- User config: `%APPDATA%/ClipboardHistory/settings.yaml`
- GitHub config: `%APPDATA%/ClipboardHistory/github_settings.yaml` (separate file)
- GitHub token: stored in Windows Credential Manager via `keyring` (never in YAML)
- `ConfigManager` loads both files and merges them; `save()` strips `github.token` before writing

## Key Design Patterns

### GitHub as Primary Storage
When GitHub sync is enabled, GitHub is primary storage and local SQLite is cache-only. On startup, the app clears local cache and pulls from GitHub.

### Callback Pattern for UI-App Communication
`ModernHistoryViewer` accepts `on_github_settings_changed` callback from `ClipboardHistoryApp._reinitialize_github_sync`. This avoids the UI reaching into app internals (Law of Demeter compliance).

### Encryption Flow
1. User sets sync password in settings dialog
2. `KeyManager.set_sync_password()` derives key using PBKDF2-HMAC-SHA256 (600k iterations, fixed salt)
3. Same password on different devices produces same encryption key
4. Content encrypted with `EncryptionManager.encrypt()` before GitHub upload

### Sync Architecture
- `backups/clipboard_sync.json` - Single encrypted file containing all entries (overwrites on each push)
- Bidirectional sync: pulls merge remote-only entries to local, then pushes local-only entries to remote
- `sync/latest.json` - Real-time sync file for push_latest/pull_latest

### Qt Thread Safety
- `QtSignalBridge` class with pyqtSignals for cross-thread communication
- Background operations (sync, cleanup) run in daemon threads
- UI updates must go through signal/slot mechanism

## Important Files

| File | Purpose |
|------|---------|
| `main_improved.py` | Entry point, `ClipboardHistoryApp`, `QtSignalBridge` |
| `ClipSyncer.spec` | PyInstaller configuration with hidden imports |
| `hook-qfluentwidgets.py` | PyInstaller hook for collecting qfluentwidgets data |
| `src/utils/config_manager.py` | Loads settings.yaml + github_settings.yaml, strips token on save |
| `src/services/sync/github_sync.py` | `upload_backup()`, `download_backup()`, `push_latest()`, `pull_latest()` |
| `src/services/auto_sync_service.py` | Real-time push (5s debounce, 30s min interval) + periodic pull (60s) |

## Common Issues

- **GitHub sync not working**: Check that `github_settings.yaml` has `enabled: true` and repository is in `username/repo` format (not full URL)
- **qfluentwidgets import errors in exe**: Ensure `collect_all('qfluentwidgets')` is in spec file
- **Encryption mismatch between devices**: Must use same sync password on all devices
- **PBKDF2 import**: Use `PBKDF2HMAC` from `cryptography.hazmat.primitives.kdf.pbkdf2`, not `PBKDF2`
