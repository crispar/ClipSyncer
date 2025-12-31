# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Collect all qfluentwidgets resources
datas = []
binaries = []
hiddenimports = []

# Collect qfluentwidgets completely
try:
    qfw_datas, qfw_binaries, qfw_hiddenimports = collect_all('qfluentwidgets')
    datas += qfw_datas
    binaries += qfw_binaries
    hiddenimports += qfw_hiddenimports
except:
    pass

# Also explicitly collect qfluentwidgets submodules
hiddenimports += collect_submodules('qfluentwidgets')

# Only collect PyQt6 data files (icons, translations), not all modules
try:
    pyqt6_datas = collect_data_files('PyQt6')
    datas += pyqt6_datas
except:
    pass

# Add config files if they exist
if os.path.exists('config'):
    datas += [('config', 'config')]

# Don't include src as data, it will be compiled
# datas += [('src', 'src')]

# Add icon if it exists
if os.path.exists('assets/icon.ico'):
    datas += [('assets/icon.ico', 'assets')]

# Additional hidden imports - comprehensive list
hiddenimports += [
    # Core PyQt6 modules
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'PyQt6.sip',

    # qfluentwidgets and all its components
    'qfluentwidgets',
    'qfluentwidgets.common',
    'qfluentwidgets.components',
    'qfluentwidgets.window',
    'qfluentwidgets.multimedia',
    'qfluentwidgets._rc',

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

    # Config
    'yaml',
    'json',

    # GitHub
    'github',
    'github.MainClass',

    # Utils
    'darkdetect',

    # Our modules
    'src',
    'src.core',
    'src.core.clipboard',
    'src.core.storage',
    'src.services',
    'src.services.archive_manager',
    'src.services.sync',
    'src.services.sync.github_sync',
    'src.ui',
    'src.ui.dialogs',
    'src.ui.dialogs.github_settings_dialog',
    'src.ui.history',
    'src.ui.history.history_viewer_modern',
    'src.ui.tray',
    'src.ui.tray.tray_icon_fluent',
    'src.utils',
]

a = Analysis(
    ['main_improved.py'],
    pathex=[os.getcwd()],  # Add current directory to path
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.'],  # Use current directory for hooks
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Data science / testing
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
        # Unused PyQt6 modules (large size savings)
        'PyQt6.QtBluetooth',
        'PyQt6.QtDBus',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtNetworkAuth',
        'PyQt6.QtNfc',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPositioning',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtQuickWidgets',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebSockets',
        # 'PyQt6.QtXml',  # Required by qfluentwidgets
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DExtras',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DRender',
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
    debug=False,  # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression for smaller file size
    upx_exclude=['qwindows.dll', 'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'python*.dll'],
    runtime_tmpdir=None,
    console=False,  # Console hidden, check logs/ folder for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None
)