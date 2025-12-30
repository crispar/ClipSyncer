# ClipboardHistory

A professional-grade clipboard history management application with encrypted cloud sync capabilities.

## Features

- **Real-time Clipboard Monitoring**: Automatically captures text copied to clipboard
- **Smart Duplicate Detection**: Automatically removes duplicate entries
- **Encrypted Storage**: All clipboard data is encrypted using industry-standard encryption
- **GitHub Sync**: Optional synchronization with GitHub repository for backup
- **System Tray Integration**: Runs silently in the background with easy access
- **Rich History Viewer**: Browse and search through clipboard history
- **Configurable Settings**: Customize retention period, encryption, and sync settings

## Architecture

```
ClipboardHistory/
├── src/
│   ├── core/              # Core business logic
│   │   ├── clipboard/      # Clipboard monitoring
│   │   ├── encryption/     # Data encryption
│   │   └── storage/        # Data persistence
│   ├── services/           # Application services
│   │   ├── sync/          # GitHub synchronization
│   │   └── cleanup/       # Duplicate removal & cleanup
│   ├── ui/                # User interface
│   │   ├── tray/          # System tray
│   │   ├── history/       # History viewer
│   │   └── settings/      # Settings dialog
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── config/               # Configuration files
└── resources/            # Icons and assets
```

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows 10/11
- Git (optional, for GitHub sync)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ClipboardHistory.git
cd ClipboardHistory
```

2. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python main.py
```

## Configuration

Configuration is stored in `config/settings.yaml`:

```yaml
clipboard:
  check_interval: 500  # milliseconds
  max_history_size: 1000

encryption:
  enabled: true
  algorithm: AES-256-GCM

github:
  enabled: false
  repository: ""
  branch: "main"

cleanup:
  duplicate_removal: true
  cleanup_interval: 3600  # seconds
```

## Building Executable

To create a standalone executable:

```bash
python build.py
```

The executable will be created in the `dist/` directory.

## Security

- All clipboard data is encrypted using AES-256-GCM
- Encryption keys are stored securely using Windows Credential Manager
- GitHub sync uses encrypted transport (HTTPS)
- No clipboard data is ever transmitted without encryption

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.