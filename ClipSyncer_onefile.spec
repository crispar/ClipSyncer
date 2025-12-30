# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

block_cipher = None

# Get the site-packages directory from venv
import site
site_packages = site.getsitepackages()[0]

# Explicitly add qfluentwidgets and pyqt6_frameless_window paths
datas = []
hiddenimports = []

# Manually add qfluentwidgets package
qfluentwidgets_path = os.path.join(site_packages, 'qfluentwidgets')
if os.path.exists(qfluentwidgets_path):
    datas.append((qfluentwidgets_path, 'qfluentwidgets'))

# Manually add qframelesswindow package (installed as qframelesswindow, not pyqt6_frameless_window)
frameless_path = os.path.join(site_packages, 'qframelesswindow')
if os.path.exists(frameless_path):
    datas.append((frameless_path, 'qframelesswindow'))

# Add config files if they exist
if os.path.exists('config'):
    datas += [('config', 'config')]

# Add icon if it exists
if os.path.exists('assets/icon.ico'):
    datas += [('assets/icon.ico', 'assets')]

# Comprehensive hidden imports list
hiddenimports = [
    # qfluentwidgets and all submodules
    'qfluentwidgets',
    'qfluentwidgets.common',
    'qfluentwidgets.common.style_sheet',
    'qfluentwidgets.common.config',
    'qfluentwidgets.common.icon',
    'qfluentwidgets.common.font',
    'qfluentwidgets.common.translator',
    'qfluentwidgets.components',
    'qfluentwidgets.components.dialog_box',
    'qfluentwidgets.components.layout',
    'qfluentwidgets.components.material',
    'qfluentwidgets.components.navigation',
    'qfluentwidgets.components.scrollbar',
    'qfluentwidgets.components.settings',
    'qfluentwidgets.components.widgets',
    'qfluentwidgets.window',
    'qfluentwidgets.multimedia',
    'qfluentwidgets._rc',

    # QFrameless Window
    'qframelesswindow',
    'qframelesswindow.windows',
    'qframelesswindow.utils',

    # Core PyQt6 modules
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'PyQt6.sip',

    # Database
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.baked',

    # Encryption
    'cryptography',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.kdf',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.backends',

    # Windows integration
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'win32com',
    'win32com.client',
    'win32api',
    'win32clipboard',
    'pywintypes',

    # System tray
    'pystray',
    'pystray._win32',

    # Images
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',

    # Logging
    'loguru',

    # Clipboard
    'pyperclip',

    # Scheduling
    'apscheduler',
    'apscheduler.schedulers',
    'apscheduler.schedulers.background',
    'schedule',

    # Config
    'yaml',
    'json',

    # GitHub
    'github',
    'github.MainClass',

    # Utils
    'darkdetect',
    'pynacl',
    'pynacl.encoding',
    'pynacl.public',

    # Our modules
    'src',
    'src.core',
    'src.core.clipboard',
    'src.core.storage',
    'src.core.storage.models',
    'src.core.storage.repository',
    'src.core.storage.encryption',
    'src.core.sync',
    'src.core.sync.github_sync',
    'src.ui',
    'src.ui.history',
    'src.ui.history.history_viewer_modern',
    'src.ui.tray',
    'src.ui.tray.tray_icon_fluent',
    'src.utils',
    'src.utils.qt_bridge',
]

a = Analysis(
    ['main_improved.py'],
    pathex=[os.getcwd(), site_packages],  # Add site-packages to path
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'tkinter',
        'test',
        'tests',
        'testing',
        'unittest',
        'pytest',
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
    name='ClipSyncer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Enable console to see errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None
)