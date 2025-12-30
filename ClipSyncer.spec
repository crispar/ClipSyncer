# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Collect all qfluentwidgets resources
datas = []
hiddenimports = []

# Collect qfluentwidgets
qfluentwidgets_datas, qfluentwidgets_binaries, qfluentwidgets_hiddenimports = collect_all('qfluentwidgets')
datas += qfluentwidgets_datas
hiddenimports += qfluentwidgets_hiddenimports

# Collect PyQt6
pyqt6_datas, pyqt6_binaries, pyqt6_hiddenimports = collect_all('PyQt6')
datas += pyqt6_datas
hiddenimports += pyqt6_hiddenimports

# Add config files
datas += [('config', 'config')]

# Add source files
datas += [('src', 'src')]

# Additional hidden imports
hiddenimports += [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    'qfluentwidgets',
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.baked',
    'cryptography',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.ciphers',
    'keyring',
    'keyring.backends.Windows',
    'pystray',
    'PIL',
    'PIL.Image',
    'loguru',
    'pyperclip',
    'apscheduler',
    'schedule',
    'yaml',
    'github',
    'darkdetect',
    'win32com',
    'win32api',
    'pynacl',
]

a = Analysis(
    ['main_improved.py'],
    pathex=[],
    binaries=qfluentwidgets_binaries + pyqt6_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None
)