# -*- mode: python ; coding: utf-8 -*-
"""
PhantomHand 后端 PyInstaller 打包配置

使用方法:
    cd python_service
    python -m PyInstaller PhantomHandBackend.spec

注意事项:
    1. 必须在 Windows 环境下打包
    2. 确保已安装所有依赖: pip install -r requirements.txt
    3. 确保已安装 PyInstaller: pip install pyinstaller
"""

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# 收集 MediaPipe 的所有文件（模型、配置等）
mediapipe_datas, mediapipe_binaries, mediapipe_hiddenimports = collect_all('mediapipe')

# 收集 OpenCV 的所有文件
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')

# 合并所有数据文件
all_datas = []
all_datas += mediapipe_datas
all_datas += cv2_datas
all_datas += [
    ('config', 'config'),  # 配置文件目录
]

# 合并所有二进制文件
all_binaries = []
all_binaries += mediapipe_binaries
all_binaries += cv2_binaries

# 合并所有隐藏导入
all_hiddenimports = [
    'mediapipe',
    'mediapipe.python',
    'mediapipe.python.solutions',
    'mediapipe.python.solutions.hands',
    'cv2',
    'numpy',
    'websockets',
    'websockets.server',
    'websockets.client',
    'asyncio',
    'json',
    'dataclasses',
    'typing',
    'queue',
    'threading',
    'ctypes',
    'ctypes.wintypes',
]
all_hiddenimports += mediapipe_hiddenimports
all_hiddenimports += cv2_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'scipy',
        'pandas',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhantomHandBackend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../assets/icon.ico',  # 图标文件（如果存在）
)
