"""GitHub Sync Setup Helper"""

import os
import sys
import yaml
from pathlib import Path
from getpass import getpass

def setup_github_sync():
    """Interactive setup for GitHub sync"""

    print("=" * 60)
    print("ClipSyncer - GitHub Sync Setup")
    print("=" * 60)
    print("\nThis will help you configure GitHub synchronization.")
    print("Your clipboard history will be encrypted and backed up to a private GitHub repository.\n")

    # Get user input
    print("Step 1: GitHub Personal Access Token")
    print("  - Go to: https://github.com/settings/tokens")
    print("  - Click 'Generate new token (classic)'")
    print("  - Select scope: 'repo' (Full control of private repositories)")
    print("  - Generate and copy the token\n")

    token = getpass("Enter your GitHub Personal Access Token: ")

    print("\nStep 2: Repository Information")
    print("  - Create a private repository at: https://github.com/new")
    print("  - Name it something like 'clipboard-backup'")
    print("  - Make sure it's PRIVATE!\n")

    username = input("Enter your GitHub username: ")
    repo_name = input("Enter repository name (e.g., clipboard-backup): ")

    print("\nStep 3: Sync Settings")
    enable_sync = input("Enable automatic sync? (y/n): ").lower() == 'y'

    if enable_sync:
        sync_interval = input("Sync interval in minutes (default: 60): ")
        sync_interval = int(sync_interval) * 60 if sync_interval else 3600
    else:
        sync_interval = 3600

    # Load existing settings
    settings_path = Path(os.environ.get('APPDATA', '.')) / 'ClipboardHistory' / 'settings.yaml'
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f) or {}
    else:
        # Load default settings
        default_path = Path(__file__).parent / 'config' / 'default_settings.yaml'
        if default_path.exists():
            with open(default_path, 'r') as f:
                settings = yaml.safe_load(f) or {}
        else:
            settings = {}

    # Update GitHub settings
    if 'github' not in settings:
        settings['github'] = {}

    settings['github']['enabled'] = enable_sync
    settings['github']['token'] = token
    settings['github']['repository'] = f"{username}/{repo_name}"
    settings['github']['branch'] = 'main'
    settings['github']['sync_interval'] = sync_interval

    # Save settings
    with open(settings_path, 'w') as f:
        yaml.dump(settings, f, default_flow_style=False)

    print("\n" + "=" * 60)
    print("✅ GitHub Sync Configuration Saved!")
    print("=" * 60)

    if enable_sync:
        print(f"\n📁 Settings saved to: {settings_path}")
        print(f"🔄 Sync enabled: Every {sync_interval // 60} minutes")
        print(f"📦 Repository: https://github.com/{username}/{repo_name}")
        print("\n⚠️  Important:")
        print("  - Keep your token secret!")
        print("  - Make sure your repository is PRIVATE")
        print("  - Restart ClipSyncer for changes to take effect")
    else:
        print("\n❌ GitHub sync is disabled")
        print("You can enable it later by running this setup again")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        setup_github_sync()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)