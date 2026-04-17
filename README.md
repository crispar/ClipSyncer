# ClipSyncer

A Windows clipboard history manager with end-to-end encrypted GitHub sync, built with PyQt6 and Fluent Design.

ClipSyncer runs in the system tray, captures everything you copy, and (optionally) syncs an encrypted history across your machines through a private GitHub repository. Your encryption key never leaves your devices.

## Features

- **Real-time clipboard monitoring** – Captures text copied to the clipboard at a configurable interval (default 500 ms).
- **Smart categorization** – Entries are auto-tagged as `text`, `url`, `file_path`, or `email`.
- **Duplicate detection** – SHA-256 content hashing dedupes entries automatically.
- **AES-256-GCM encryption** – All clipboard data is encrypted before it is written to disk or uploaded.
- **GitHub sync (end-to-end encrypted)** – Real-time push (5 s debounce, 30 s minimum interval) + periodic pull (60 s). Supports GitHub.com and GitHub Enterprise.
- **Multi-device key derivation** – A shared sync password is turned into the same AES key on every device via PBKDF2-HMAC-SHA256 (600,000 iterations).
- **System tray app** – Fluent Design tray icon with quick actions (show history, toggle monitoring, manual sync, run cleanup, quit).
- **Modern history viewer** – Search, filter by category, preview, copy, delete, favorite, import/export (JSON), and clear history.
- **Archive manager** – Entries that exceed the history size are archived locally (and optionally to GitHub) with a 7-day retention.
- **Cleanup service** – Periodic duplicate removal, old-data purge, and SQLite VACUUM.
- **Corporate network friendly** – Custom CA bundle path and optional SSL-verification toggle for MITM proxies.
- **Windows Credential Manager integration** – GitHub token and encryption keys are stored via `keyring`, never in YAML.

## Requirements

- Windows 10 / 11
- Python 3.10+ (CI builds on 3.11)
- A GitHub account if you want cloud sync (a private repository is strongly recommended)

## Installation

### Option 1 – Run the prebuilt executable

Download `ClipSyncer.exe` from the [Releases](../../releases) page (produced by the GitHub Actions build workflow on tagged releases) and run it. No Python required.

### Option 2 – Run from source

```bash
git clone <repository-url>
cd ClipSyncer

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
python main_improved.py
```

A convenience script is provided:

```bash
run.bat
```

## Quick start

1. Launch ClipSyncer. On first run, a welcome dialog appears.
2. Choose **Setup GitHub Storage** (for multi-device sync) or **Use Local Storage Only**.
3. If you picked GitHub sync, fill in the GitHub settings dialog (see below).
4. ClipSyncer minimizes to the system tray. Copy anything – it is captured automatically.
5. Right-click the tray icon → **Show History** (or double-click the icon) to browse entries.

### Keyboard shortcuts (history viewer)

| Shortcut | Action                          |
| -------- | ------------------------------- |
| `Ctrl+C` | Copy selected entry to clipboard |
| `Ctrl+F` | Focus search                    |
| `Delete` | Delete selected entry           |
| `F5`     | Refresh list                    |
| `Esc`    | Close window (app stays in tray) |

### Tray menu

- Show History
- Toggle Monitoring (pause / resume capture)
- Sync to GitHub (manual push)
- Run Cleanup
- Quit

## Setting up GitHub sync

1. **Create a private repository** (e.g. `clipboard-backup`) on GitHub.com or your GitHub Enterprise instance. Keep it private – it will hold your encrypted clipboard data.
2. **Create a Personal Access Token**
   - Go to `Settings → Developer settings → Personal access tokens → Tokens (classic)`.
   - Generate a token with the `repo` scope.
3. **Configure ClipSyncer**
   - From the tray or the history viewer open **GitHub Sync Settings**.
   - Enter repository (`username/repo` or full URL), paste the token, and set a **sync password**.
   - Click **Test Connection**, then save.
4. **Repeat on every device** using the **same sync password** so all devices derive the same AES key and can read each other’s entries.

### GitHub Enterprise

Set `github.enterprise_url` in `github_settings.yaml` (e.g. `https://github.example.com`). The client will use `/{enterprise_url}/api/v3`.

### Corporate TLS / MITM proxies

- `github.ca_bundle_path`: path to a PEM bundle containing your corporate root CA.
- `github.verify_ssl`: set to `false` only as a last resort.
- The client also honors `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and `CURL_CA_BUNDLE` environment variables, and falls back to `certifi`.

## Configuration

Settings are split across two files, both under `%APPDATA%/ClipboardHistory/`:

- `settings.yaml` – application settings (seeded from `config/default_settings.yaml`)
- `github_settings.yaml` – GitHub-specific settings (example in `config/github_settings_example.yaml`)

Secrets (GitHub token, encryption keys) are stored in **Windows Credential Manager** via `keyring` and are never written to YAML.

### Full defaults

```yaml
clipboard:
  check_interval: 500        # ms between clipboard polls
  max_history_size: 500      # max entries kept before archival
  auto_start: true

encryption:
  enabled: true
  algorithm: AES-256-GCM

storage:
  retention_days: 30         # purge entries older than this
  backup_interval: 86400     # seconds (24 h)
  database_path: null        # null → %APPDATA%/ClipboardHistory/clipboard.db

github:
  enabled: false
  repository: ""             # "username/repo" or full URL
  token: ""                  # kept in keyring, not YAML
  sync_interval: 3600        # legacy
  auto_sync: false           # legacy – real-time push + periodic pull is used instead
  pull_interval: 60          # seconds between pulls
  push_debounce: 5           # seconds after clipboard change before pushing
  min_push_interval: 30      # minimum seconds between pushes
  ca_bundle_path: ""         # corporate CA bundle (PEM)
  verify_ssl: true           # disable only in closed corporate networks
  # enterprise_url: ""       # e.g. https://github.example.com

cleanup:
  enabled: true
  duplicate_removal: true
  cleanup_interval: 3600     # seconds between cleanup runs

ui:
  show_notifications: true
  minimize_to_tray: true
  start_minimized: false
  theme: light               # light | dark

logging:
  level: INFO                # DEBUG | INFO | WARNING | ERROR
  file_logging: true
  max_log_size: 10485760     # 10 MB per file
  max_log_files: 5
```

## Data & log locations

| What               | Path                                                                   |
| ------------------ | ---------------------------------------------------------------------- |
| Settings           | `%APPDATA%/ClipboardHistory/settings.yaml`                             |
| GitHub settings    | `%APPDATA%/ClipboardHistory/github_settings.yaml`                      |
| SQLite database    | `%APPDATA%/ClipboardHistory/clipboard.db`                              |
| Local archives     | `%APPDATA%/ClipboardHistory/archives/`                                 |
| Daily logs         | `%APPDATA%/ClipboardHistory/logs/ClipSyncer_YYYY-MM-DD.log`            |
| Latest log (10 MB) | `%APPDATA%/ClipboardHistory/logs/ClipSyncer_latest.log`                |
| Encryption key     | Windows Credential Manager (via `keyring`)                             |
| GitHub token       | Windows Credential Manager (via `keyring`)                             |

When running from source without setting `%APPDATA%`, logs fall back to `./logs/`.

## Architecture

```
ClipSyncer/
├── main_improved.py          # Entry point – orchestrates the app and tray
├── build.py                  # PyInstaller build + optional NSIS installer script
├── ClipSyncer.spec           # PyInstaller spec (with qfluentwidgets hooks)
├── hook-qfluentwidgets.py    # PyInstaller runtime hook
├── requirements.txt          # Dev + runtime dependencies
├── requirements-prod.txt     # Runtime-only dependencies
├── run.bat                   # Dev launcher (activates venv)
├── version_info.txt          # Windows version resource
├── config/
│   ├── default_settings.yaml
│   └── github_settings_example.yaml
├── assets/
│   └── icon.ico
├── src/
│   ├── core/
│   │   ├── clipboard/        # ClipboardMonitor, ClipboardHistory, ClipboardEntry
│   │   ├── encryption/       # EncryptionManager (AES-256-GCM), KeyManager (keyring + PBKDF2)
│   │   ├── storage/          # DatabaseManager (SQLAlchemy), ClipboardRepository
│   │   ├── interfaces.py     # ABCs: EncryptionStrategy, SyncBackend, StorageBackend
│   │   └── exceptions.py     # ClipSyncerError hierarchy
│   ├── services/
│   │   ├── component_factory.py   # Wires components together (DI)
│   │   ├── sync_coordinator.py    # Bidirectional push / pull / merge
│   │   ├── auto_sync_service.py   # Real-time push (debounced) + periodic pull
│   │   ├── archive_manager.py     # Archives overflow / aged entries
│   │   ├── sync/github_sync.py    # GitHubSyncService (supports Enterprise)
│   │   └── cleanup/               # CleanupService, DuplicateRemover, OldDataCleaner
│   ├── ui/
│   │   ├── tray/             # Fluent Design system tray icon
│   │   ├── history/          # ModernHistoryViewer (qfluentwidgets)
│   │   └── dialogs/          # Welcome, GitHub settings, App settings, Restore
│   └── utils/
│       └── config_manager.py # Loads & merges settings.yaml + github_settings.yaml
├── tests/                    # pytest suite (17 modules)
└── .github/workflows/build.yml  # CI: build .exe and attach to releases
```

### Key design choices

- **Dependency inversion** – Core code depends on ABCs (`EncryptionStrategy`, `SyncBackend`, `StorageBackend`); concrete classes (e.g. `GitHubSyncService`) are injected by `ComponentFactory`.
- **Single-file sync model** – The remote state lives in a single encrypted JSON (`backups/clipboard_sync.json`) that is overwritten on every push and merged on pull.
- **GitHub as primary storage** – When sync is enabled, `SyncCoordinator.initial_sync()` clears the local cache on startup and pulls from GitHub, treating the repo as source of truth.
- **Qt thread safety** – Background work runs in daemon threads; UI updates go through a `QtSignalBridge` that forwards to the Qt event loop via signals/slots.

## Auto-sync behavior

- **Push:** Triggered on every captured clipboard change. Debounced for 5 s (latest wins) and rate-limited to at most one push per 30 s.
- **Pull:** A background timer pulls from GitHub every 60 s (configurable via `pull_interval`). An initial pull runs 5 s after startup.
- **Manual sync:** Available from the tray menu; bypasses the debounce.

## Security model

- Clipboard content is encrypted with **AES-256-GCM** (authenticated) before being written to SQLite or uploaded.
- The AES key is derived from the **sync password** via **PBKDF2-HMAC-SHA256** (600,000 iterations) so the same password on any device produces the same key.
- Keys and GitHub tokens live in **Windows Credential Manager**; only the derived artifacts touch disk.
- A wrong sync password raises `DecryptionError` with a clear message – no silent corruption.
- **Use a private GitHub repository.** The repository only stores ciphertext, but you should still not expose it publicly.

## Development

### Run the test suite

```bash
pytest                    # all tests
pytest -v                 # verbose
pytest tests/test_github_sync.py
pytest --cov              # coverage (pytest-cov is pinned in requirements.txt)
```

### Lint / format / type-check

```bash
black .
flake8
mypy .
```

### Build the Windows executable

```bash
python build.py
```

This:

1. Cleans `build/` and `dist/`.
2. Regenerates `version_info.txt`.
3. Runs `pyinstaller ClipSyncer.spec --clean --noconfirm`.
4. Emits `dist/ClipSyncer.exe`.
5. Writes an `installer.nsi` NSIS script you can compile with `makensis installer.nsi` for a traditional installer.

### CI

`.github/workflows/build.yml` builds the executable on every push and PR to `main`/`master` and, for tags matching `v*`, attaches `ClipSyncer.exe` to a GitHub Release.

## Troubleshooting

- **"GitHub sync not working"** – Confirm `github.enabled: true` and that `repository` is `username/repo` (not a full URL). Use **Test Connection** in the GitHub settings dialog.
- **"DecryptionError: wrong encryption key"** – The sync password does not match the one used to encrypt the data. Enter the same password you used on your other devices.
- **qfluentwidgets import errors in the built exe** – Rebuild with `python build.py`; `ClipSyncer.spec` uses `collect_data_files('qfluentwidgets')` to bundle required assets.
- **SSL errors behind a corporate proxy** – Set `github.ca_bundle_path` to your corporate CA bundle, or export `REQUESTS_CA_BUNDLE`. As a last resort, set `github.verify_ssl: false`.
- **Where are the logs?** – `%APPDATA%/ClipboardHistory/logs/ClipSyncer_latest.log` (and daily rotated files).

## License

MIT License.
