"""
PyInstaller hook for qfluentwidgets
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Collect everything from qfluentwidgets
datas, binaries, hiddenimports = collect_all('qfluentwidgets')

# Also explicitly collect submodules
hiddenimports += collect_submodules('qfluentwidgets')

# Make sure to include all qfluentwidgets components
hiddenimports += [
    'qfluentwidgets',
    'qfluentwidgets.common',
    'qfluentwidgets.components',
    'qfluentwidgets.window',
    'qfluentwidgets.multimedia',
    'qfluentwidgets._rc',
    'qfluentwidgets.common.style_sheet',
    'qfluentwidgets.common.config',
    'qfluentwidgets.common.icon',
    'qfluentwidgets.common.font',
    'qfluentwidgets.common.translator',
    'qfluentwidgets.components.dialog_box',
    'qfluentwidgets.components.layout',
    'qfluentwidgets.components.material',
    'qfluentwidgets.components.navigation',
    'qfluentwidgets.components.scrollbar',
    'qfluentwidgets.components.settings',
    'qfluentwidgets.components.widgets',
]