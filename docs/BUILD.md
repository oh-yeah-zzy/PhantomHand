# PhantomHand 打包指南

本文档介绍如何将 PhantomHand 打包成 Windows 可执行文件。

## 📋 环境要求

### 必须安装

| 工具 | 版本要求 | 下载地址 |
|------|---------|---------|
| Python | 3.9+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| Rust | latest | https://rustup.rs |
| Visual Studio Build Tools | 2019+ | https://visualstudio.microsoft.com/visual-cpp-build-tools/ |

### 验证安装

```powershell
python --version    # Python 3.9+
node --version      # v18.0.0+
cargo --version     # cargo 1.70+
```

## 🚀 快速打包

### 方式一：使用打包脚本（推荐）

**PowerShell:**
```powershell
cd PhantomHand
.\scripts\build-windows.ps1
```

**CMD:**
```cmd
cd PhantomHand
scripts\build-windows.bat
```

### 方式二：手动打包

#### 步骤 1: 打包 Python 后端

```powershell
cd python_service

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 打包
python -m PyInstaller PhantomHandBackend.spec --noconfirm

# 复制到 Tauri sidecar 目录
mkdir ..\tauri_app\src-tauri\binaries -Force
copy dist\PhantomHandBackend.exe ..\tauri_app\src-tauri\binaries\PhantomHandBackend-x86_64-pc-windows-msvc.exe
```

#### 步骤 2: 打包前端 + Tauri

```powershell
cd tauri_app

# 安装依赖
npm install

# 构建
npm run tauri build
```

## 📦 输出文件

打包完成后，安装包位于：

```
tauri_app/src-tauri/target/release/bundle/
├── msi/
│   └── PhantomHand_0.1.0_x64_en-US.msi    # MSI 安装包
└── nsis/
    └── PhantomHand_0.1.0_x64-setup.exe    # NSIS 安装包
```

## 🔧 打包配置说明

### PyInstaller 配置 (`python_service/PhantomHandBackend.spec`)

```python
# 关键配置
exe = EXE(
    ...
    name='PhantomHandBackend',
    console=False,           # 不显示控制台
    icon='../assets/icon.ico',
)
```

### Tauri 配置 (`tauri_app/src-tauri/tauri.conf.json`)

```json
{
  "tauri": {
    "bundle": {
      "externalBin": ["binaries/PhantomHandBackend"],
      "targets": ["msi", "nsis"]
    }
  }
}
```

## ⚠️ 常见问题

### 1. MediaPipe 资源缺失

**症状:** 运行时报错 "Cannot find calculator graph config"

**解决:**
```python
# 在 spec 文件中添加
mediapipe_datas, mediapipe_binaries, mediapipe_hiddenimports = collect_all('mediapipe')
```

### 2. OpenCV DLL 缺失

**症状:** 运行时报错 "DLL load failed"

**解决:**
```python
# 在 spec 文件中添加
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
```

### 3. 杀毒软件误报

**症状:** 打包的 exe 被杀毒软件拦截

**解决:**
- 使用代码签名证书签名 exe
- 或将 exe 添加到杀毒软件白名单

### 4. 后端无法启动

**症状:** 前端显示 "未连接"

**排查步骤:**
1. 单独运行后端 exe 测试
2. 检查 8765 端口是否被占用
3. 查看 Tauri 日志输出

### 5. 摄像头权限问题

**症状:** 打开应用后摄像头不工作

**解决:**
- 确保 Windows 设置中允许应用访问摄像头
- 以管理员身份运行

## 📝 高级选项

### 调试模式打包

```powershell
.\scripts\build-windows.ps1 -Debug
```

### 仅打包后端

```powershell
.\scripts\build-windows.ps1 -SkipFrontend
```

### 仅打包前端

```powershell
.\scripts\build-windows.ps1 -SkipBackend
```

### 自定义图标

将图标文件放在以下位置：
- `assets/icon.ico` - Windows 图标
- `tauri_app/src-tauri/icons/` - Tauri 图标集

## 🔄 CI/CD 集成

### GitHub Actions 示例

```yaml
name: Build Windows

on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Setup Rust
        uses: dtolnay/rust-action@stable

      - name: Build
        run: .\scripts\build-windows.ps1

      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: PhantomHand-Windows
          path: tauri_app/src-tauri/target/release/bundle/
```

## 📚 参考链接

- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
- [Tauri 打包指南](https://tauri.app/v1/guides/building/)
- [MediaPipe 部署](https://google.github.io/mediapipe/getting_started/python.html)
