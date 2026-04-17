# ClipSyncer

A Windows clipboard history manager with encrypted GitHub sync, built with PyQt6 and Fluent Design.

## Features

- **Real-time Clipboard Monitoring** - Automatically captures text copied to clipboard
- **Smart Duplicate Detection** - Deduplicates entries via content hash (SHA-256)
- **AES-256-GCM Encryption** - All clipboard data encrypted at rest and in transit
- **GitHub Sync** - Bidirectional sync with GitHub (supports GitHub Enterprise)
- **System Tray Integration** - Runs in background with Windows 11 Fluent Design tray icon
- **Rich History Viewer** - Browse, search, filter, and manage clipboard history
- **Keyboard Shortcuts** - Ctrl+C (copy), Ctrl+F (search), Delete, Escape, F5 (refresh)
- **Archive Manager** - Automatically archives overflow entries with 7-day retention
- **Configurable Settings** - Theme, check interval, max history, retention days

## Project Structure

```
ClipSyncer/
├── main_improved.py          # Entry point (used by PyInstaller)
├── build.py                  # Build script (PyInstaller + NSIS)
├── ClipSyncer.spec           # PyInstaller spec file
├── hook-qfluentwidgets.py    # PyInstaller hook for qfluentwidgets
├── requirements.txt          # Python dependencies
├── config/
│   ├── default_settings.yaml     # Default configuration
│   └── github_settings_example.yaml
├── assets/
│   └── icon.ico              # Application icon
├── src/
│   ├── core/
│   │   ├── clipboard/        # ClipboardMonitor, ClipboardHistory
│   │   ├── encryption/       # EncryptionManager (AES-256-GCM), KeyManager
│   │   └── storage/          # DatabaseManager (SQLite), ClipboardRepository
│   ├── services/
│   │   ├── sync/             # GitHubSyncService
│   │   ├── cleanup/          # CleanupService, DuplicateRemover, OldDataCleaner
│   │   ├── auto_sync_service.py  # Real-time push/pull sync
│   │   └── archive_manager.py    # Overflow entry archival
│   ├── ui/
│   │   ├── tray/             # ModernTrayIcon (QSystemTrayIcon, Fluent Design)
│   │   ├── history/          # ModernHistoryViewer (qfluentwidgets)
│   │   └── dialogs/          # GitHub settings, welcome, app settings, restore
│   └── utils/
│       └── config_manager.py # YAML config loader
└── tests/                    # Test suite (pytest)
```

## Installation

### Prerequisites

- Python 3.10+
- Windows 10/11

### Setup

```bash
git clone <repository-url>
cd ClipSyncer

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### Run

```bash
python main_improved.py
```

Or use the batch file:
```bash
run.bat
```

## Configuration

User configuration is stored at `%APPDATA%/ClipboardHistory/settings.yaml`.
GitHub settings are stored separately at `%APPDATA%/ClipboardHistory/github_settings.yaml`.
GitHub token and encryption keys are stored securely in Windows Credential Manager via `keyring`.

### Default Settings

```yaml
clipboard:
  check_interval: 500   # ms
  max_history_size: 500

encryption:
  enabled: true
  algorithm: AES-256-GCM

storage:
  retention_days: 30

github:
  enabled: false
  repository: ""         # format: username/repo
  ca_bundle_path: ""     # optional corporate root CA (.crt/.pem) for MITM proxies
  verify_ssl: true       # set to false ONLY as a last resort in closed networks

cleanup:
  duplicate_removal: true
  cleanup_interval: 3600  # seconds

ui:
  show_notifications: true
  theme: light            # light or dark
```

## Building Executable

```bash
python build.py
```

Output: `dist/ClipSyncer.exe`

## Corporate Networks (TLS inspection)

If your workplace uses an HTTPS MITM proxy (Zscaler, Bluecoat, corporate TLS
inspection, etc.), GitHub sync may fail with:

```
Failed to download backup: Could not find a suitable TLS CA certificate bundle, invalid path:
```

Fix it by pointing ClipSyncer at your corporate root CA:

1. Export the corporate root CA from Windows's Trusted Root Certification
   Authorities store as a `.crt` / `.pem` file (ask IT if unsure).
2. Open **GitHub Sync Settings** in ClipSyncer and set **Corporate CA bundle**
   to that file (or click **Browse...**).
3. Click **Test Connection** to verify.

Alternatively, set the `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` environment
variable before launching, or edit `%APPDATA%/ClipboardHistory/github_settings.yaml`:

```yaml
github:
  ca_bundle_path: "C:/corp/ca-bundle.crt"
  verify_ssl: true
```

Resolution order: `ca_bundle_path` → env vars → bundled `certifi` → system default.

## Security

- All clipboard data encrypted with AES-256-GCM before storage and sync
- Encryption keys stored in Windows Credential Manager (not in config files)
- PBKDF2-HMAC-SHA256 (600k iterations) for sync password key derivation
- Same sync password on different devices produces the same encryption key
- GitHub token stored in keyring, never written to YAML files

## License

MIT License
