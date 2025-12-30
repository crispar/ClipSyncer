"""Build script for creating executable"""

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

    # Remove spec files
    for spec_file in Path('.').glob('*.spec'):
        spec_file.unlink()
        print(f"  Removed {spec_file}")


def create_icon():
    """Create application icon"""
    print("Creating application icon...")

    icon_script = '''
from PIL import Image, ImageDraw

# Create icon at multiple sizes
sizes = [16, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Scale factor
    scale = size / 64.0

    # Draw clipboard
    clipboard_color = (70, 130, 180)
    draw.rectangle(
        [10*scale, 5*scale, 54*scale, 59*scale],
        fill=clipboard_color
    )
    draw.rectangle(
        [20*scale, 0, 44*scale, 10*scale],
        fill=clipboard_color
    )

    # Draw clip
    clip_color = (192, 192, 192)
    draw.rectangle(
        [25*scale, 0, 39*scale, 15*scale],
        fill=clip_color
    )

    images.append(img)

# Save as ICO file
if images:
    images[0].save(
        'resources/icon.ico',
        format='ICO',
        sizes=[(img.width, img.height) for img in images]
    )
    print("  Icon created: resources/icon.ico")
'''

    # Create resources directory
    os.makedirs('resources', exist_ok=True)

    # Execute icon creation
    exec(icon_script)


def create_pyinstaller_spec():
    """Create PyInstaller spec file"""
    print("Creating PyInstaller spec file...")

    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/default_settings.yaml', 'config'),
        ('resources/icon.ico', 'resources'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'pystray._win32',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'sqlalchemy.ext.declarative',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives.ciphers',
        'github',
        'apscheduler.schedulers.background',
        'keyring.backends.Windows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ClipboardHistory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
    version='version_info.txt'
)
'''

    with open('ClipboardHistory.spec', 'w') as f:
        f.write(spec_content)

    print("  Spec file created: ClipboardHistory.spec")


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

    # Activate virtual environment for build
    venv_python = Path('venv/Scripts/python.exe')

    if venv_python.exists():
        python_exe = str(venv_python)
    else:
        python_exe = sys.executable

    # Run PyInstaller
    cmd = [
        python_exe,
        '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'ClipboardHistory.spec'
    ]

    print(f"  Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("  Build successful!")
            print(f"  Executable created: dist/ClipboardHistory.exe")
        else:
            print(f"  Build failed with error code {result.returncode}")
            print(f"  Error output: {result.stderr}")
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
    print("ClipboardHistory Build Script")
    print("=" * 60)

    # Step 1: Clean
    clean_build()

    # Step 2: Create icon
    create_icon()

    # Step 3: Create version info
    create_version_info()

    # Step 4: Create PyInstaller spec
    create_pyinstaller_spec()

    # Step 5: Build executable
    if build_executable():
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("=" * 60)
        print("\nExecutable location: dist/ClipboardHistory.exe")

        # Step 6: Create installer script (optional)
        create_installer_script()

        print("\nNext steps:")
        print("1. Test the executable: dist/ClipboardHistory.exe")
        print("2. Create installer: makensis installer.nsi")
    else:
        print("\n" + "=" * 60)
        print("BUILD FAILED!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()