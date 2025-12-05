# PhantomHand Windows 打包脚本
# 使用方法: 在 PowerShell 中执行 .\scripts\build-windows.ps1

param(
    [switch]$SkipBackend,    # 跳过后端打包
    [switch]$SkipFrontend,   # 跳过前端打包
    [switch]$Debug           # 调试模式
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PhantomHand Windows 打包脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查必要工具
function Test-Command($Command) {
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

Write-Host "[1/5] 检查环境..." -ForegroundColor Yellow

if (-not (Test-Command "python")) {
    Write-Host "错误: 未找到 Python，请安装 Python 3.9+" -ForegroundColor Red
    exit 1
}

if (-not (Test-Command "node")) {
    Write-Host "错误: 未找到 Node.js，请安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

if (-not (Test-Command "cargo")) {
    Write-Host "错误: 未找到 Rust/Cargo，请安装 Rust" -ForegroundColor Red
    exit 1
}

Write-Host "  Python: $(python --version)" -ForegroundColor Green
Write-Host "  Node: $(node --version)" -ForegroundColor Green
Write-Host "  Cargo: $(cargo --version)" -ForegroundColor Green
Write-Host ""

# ========== 步骤 2: 打包 Python 后端 ==========
if (-not $SkipBackend) {
    Write-Host "[2/5] 打包 Python 后端..." -ForegroundColor Yellow

    Push-Location "$ProjectRoot\python_service"

    # 创建虚拟环境（如果不存在）
    if (-not (Test-Path ".venv")) {
        Write-Host "  创建虚拟环境..." -ForegroundColor Gray
        python -m venv .venv
    }

    # 激活虚拟环境
    Write-Host "  激活虚拟环境..." -ForegroundColor Gray
    & .\.venv\Scripts\Activate.ps1

    # 安装依赖
    Write-Host "  安装依赖..." -ForegroundColor Gray
    pip install -r requirements.txt -q
    pip install pyinstaller -q

    # 执行 PyInstaller 打包
    Write-Host "  执行 PyInstaller 打包..." -ForegroundColor Gray
    if ($Debug) {
        python -m PyInstaller PhantomHandBackend.spec --noconfirm
    } else {
        python -m PyInstaller PhantomHandBackend.spec --noconfirm 2>&1 | Out-Null
    }

    # 检查输出
    if (Test-Path "dist\PhantomHandBackend.exe") {
        $FileSize = (Get-Item "dist\PhantomHandBackend.exe").Length / 1MB
        Write-Host "  后端打包成功: dist\PhantomHandBackend.exe ($([math]::Round($FileSize, 2)) MB)" -ForegroundColor Green
    } else {
        Write-Host "  错误: 后端打包失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }

    # 复制到 Tauri sidecar 目录
    $SidecarDir = "$ProjectRoot\tauri_app\src-tauri\binaries"
    if (-not (Test-Path $SidecarDir)) {
        New-Item -ItemType Directory -Path $SidecarDir | Out-Null
    }

    # 根据平台命名 (Tauri 要求格式: name-target_triple)
    $TargetTriple = "x86_64-pc-windows-msvc"
    Copy-Item "dist\PhantomHandBackend.exe" "$SidecarDir\PhantomHandBackend-$TargetTriple.exe" -Force
    Write-Host "  已复制到 Tauri sidecar 目录" -ForegroundColor Green

    Pop-Location
    Write-Host ""
} else {
    Write-Host "[2/5] 跳过后端打包" -ForegroundColor Gray
    Write-Host ""
}

# ========== 步骤 3: 安装前端依赖 ==========
Write-Host "[3/5] 安装前端依赖..." -ForegroundColor Yellow

Push-Location "$ProjectRoot\tauri_app"

if (-not (Test-Path "node_modules")) {
    npm install
} else {
    Write-Host "  node_modules 已存在，跳过安装" -ForegroundColor Gray
}

Pop-Location
Write-Host ""

# ========== 步骤 4: 构建前端 ==========
if (-not $SkipFrontend) {
    Write-Host "[4/5] 构建前端..." -ForegroundColor Yellow

    Push-Location "$ProjectRoot\tauri_app"

    npm run build

    if (Test-Path "dist") {
        Write-Host "  前端构建成功" -ForegroundColor Green
    } else {
        Write-Host "  错误: 前端构建失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }

    Pop-Location
    Write-Host ""
} else {
    Write-Host "[4/5] 跳过前端构建" -ForegroundColor Gray
    Write-Host ""
}

# ========== 步骤 5: Tauri 打包 ==========
Write-Host "[5/5] Tauri 打包..." -ForegroundColor Yellow

Push-Location "$ProjectRoot\tauri_app"

if ($Debug) {
    npm run tauri build -- --debug
} else {
    npm run tauri build
}

# 查找输出文件
$MsiPath = Get-ChildItem "src-tauri\target\release\bundle\msi\*.msi" -ErrorAction SilentlyContinue | Select-Object -First 1
$NsisPath = Get-ChildItem "src-tauri\target\release\bundle\nsis\*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  打包完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($MsiPath) {
    $MsiSize = (Get-Item $MsiPath.FullName).Length / 1MB
    Write-Host "MSI 安装包: $($MsiPath.FullName)" -ForegroundColor Green
    Write-Host "  大小: $([math]::Round($MsiSize, 2)) MB" -ForegroundColor Gray
}

if ($NsisPath) {
    $NsisSize = (Get-Item $NsisPath.FullName).Length / 1MB
    Write-Host "NSIS 安装包: $($NsisPath.FullName)" -ForegroundColor Green
    Write-Host "  大小: $([math]::Round($NsisSize, 2)) MB" -ForegroundColor Gray
}

Write-Host ""
Write-Host "提示: 安装包位于 tauri_app\src-tauri\target\release\bundle\" -ForegroundColor Yellow
