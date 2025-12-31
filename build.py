"""Build script for ClipSyncer executable"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")

    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed {dir_name}/")

    # Clean Python cache files but keep spec files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                os.remove(os.path.join(root, file))
        for dir_name in dirs:
            if dir_name == '__pycache__':
                shutil.rmtree(os.path.join(root, dir_name))


def check_icon():
    """Check if icon exists"""
    icon_path = Path('assets/icon.ico')
    if icon_path.exists():
        print(f"  Icon found: {icon_path}")
        return True
    else:
        print(f"  Warning: Icon not found at {icon_path}")
        return False


def create_version_info():
    """Create version information file"""
    print("Creating version information...")

    version_info = '''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'ClipboardHistory'),
            StringStruct(u'FileDescription', u'Clipboard History Manager'),
            StringStruct(u'FileVersion', u'1.0.0.0'),
            StringStruct(u'InternalName', u'ClipboardHistory'),
            StringStruct(u'LegalCopyright', u'© 2024 ClipboardHistory. All rights reserved.'),
            StringStruct(u'OriginalFilename', u'ClipboardHistory.exe'),
            StringStruct(u'ProductName', u'ClipboardHistory'),
            StringStruct(u'ProductVersion', u'1.0.0.0')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''

    with open('version_info.txt', 'w') as f:
        f.write(version_info)

    print("  Version info created: version_info.txt")


def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable with PyInstaller...")

    # Check if spec file exists
    spec_file = 'ClipSyncer.spec'
    if not Path(spec_file).exists():
        print(f"  Error: {spec_file} not found!")
        return False

    # Run PyInstaller - try venv first, then system
    venv_pyinstaller = Path('./venv/Scripts/pyinstaller.exe')
    if venv_pyinstaller.exists():
        cmd = [str(venv_pyinstaller), spec_file, '--clean', '--noconfirm']
    else:
        cmd = [sys.executable, '-m', 'PyInstaller', spec_file, '--clean', '--noconfirm']

    print(f"  Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("  Build successful!")

            # Check if exe was created
            exe_name = 'ClipSyncer.exe' if os.name == 'nt' else 'ClipSyncer'
            exe_path = Path('dist') / exe_name
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / (1024 * 1024)
                print(f"  Executable created: {exe_path}")
                print(f"  Size: {size_mb:.2f} MB")
            else:
                print("  Warning: Executable not found in dist/")
                return False
        else:
            print(f"  Build failed with error code {result.returncode}")
            if result.stderr:
                print(f"  Error output:\n{result.stderr}")
            if result.stdout:
                print(f"  Output:\n{result.stdout}")
            return False

    except FileNotFoundError:
        print("  Error: PyInstaller not found!")
        print("  Please install PyInstaller: pip install pyinstaller")
        return False
    except Exception as e:
        print(f"  Build error: {e}")
        return False

    return True


def create_installer_script():
    """Create NSIS installer script"""
    print("Creating installer script...")

    nsis_script = '''
!define APP_NAME "ClipboardHistory"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "ClipboardHistory Team"
!define APP_WEB_SITE "https://github.com/yourusername/ClipboardHistory"
!define APP_UNINST_KEY "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APP_NAME}"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "ClipboardHistory_Setup_${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES\\${APP_NAME}"
InstallDirRegKey HKLM "Software\\${APP_NAME}" "InstallDir"
RequestExecutionLevel admin

; Pages
Page components
Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

; Installer sections
Section "${APP_NAME} (required)"
  SectionIn RO

  SetOutPath "$INSTDIR"
  File "dist\\ClipboardHistory.exe"

  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\ClipboardHistory.exe"
  CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\\uninstall.exe"

  ; Write registry keys
  WriteRegStr HKLM "${APP_UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${APP_UNINST_KEY}" "UninstallString" "$INSTDIR\\uninstall.exe"
  WriteRegStr HKLM "${APP_UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${APP_UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${APP_UNINST_KEY}" "URLInfoAbout" "${APP_WEB_SITE}"
SectionEnd

Section "Start Menu Shortcuts"
  CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\ClipboardHistory.exe"
SectionEnd

Section "Desktop Shortcut"
  CreateShortcut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\ClipboardHistory.exe"
SectionEnd

Section "Run at Windows startup"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "${APP_NAME}" "$INSTDIR\\ClipboardHistory.exe"
SectionEnd

; Uninstaller section
Section "Uninstall"
  ; Remove files
  Delete "$INSTDIR\\ClipboardHistory.exe"
  Delete "$INSTDIR\\uninstall.exe"

  ; Remove shortcuts
  Delete "$SMPROGRAMS\\${APP_NAME}\\*.*"
  Delete "$DESKTOP\\${APP_NAME}.lnk"

  ; Remove directories
  RMDir "$SMPROGRAMS\\${APP_NAME}"
  RMDir "$INSTDIR"

  ; Remove registry keys
  DeleteRegKey HKLM "${APP_UNINST_KEY}"
  DeleteRegKey HKLM "Software\\${APP_NAME}"
  DeleteRegValue HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Run" "${APP_NAME}"
SectionEnd
'''

    with open('installer.nsi', 'w') as f:
        f.write(nsis_script)

    print("  Installer script created: installer.nsi")
    print("  Note: Install NSIS and run 'makensis installer.nsi' to create installer")


def main():
    """Main build process"""
    print("=" * 60)
    print("ClipSyncer Build Script")
    print("=" * 60)

    # Step 1: Clean
    clean_build()

    # Step 2: Check icon
    print("\nChecking assets...")
    check_icon()

    # Step 3: Build executable
    print()
    if build_executable():
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("=" * 60)
        print("\nExecutable location: dist/ClipSyncer.exe")

        print("\nNext steps:")
        print("1. Test the executable: dist\\ClipSyncer.exe")
        print("2. Commit and push to GitHub for automatic builds")
        print("3. Create a release tag (e.g., v1.0.0) to trigger release")
    else:
        print("\n" + "=" * 60)
        print("BUILD FAILED!")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Make sure you have all dependencies: pip install -r requirements.txt")
        print("2. Check if antivirus is blocking PyInstaller")
        print("3. Try running as administrator")
        sys.exit(1)


if __name__ == "__main__":
    main()