@echo off
REM PhantomHand Windows 打包脚本 (CMD 版本)
REM 使用方法: 双击运行或在命令行执行 scripts\build-windows.bat

echo ========================================
echo   PhantomHand Windows 打包脚本
echo ========================================
echo.

REM 获取项目根目录
cd /d "%~dp0\.."
set PROJECT_ROOT=%CD%

echo [1/5] 检查环境...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 错误: 未找到 Python，请安装 Python 3.9+
    pause
    exit /b 1
)

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 错误: 未找到 Node.js，请安装 Node.js 18+
    pause
    exit /b 1
)

where cargo >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 错误: 未找到 Rust/Cargo，请安装 Rust
    pause
    exit /b 1
)

echo   环境检查通过
echo.

REM ========== 步骤 2: 打包 Python 后端 ==========
echo [2/5] 打包 Python 后端...

cd "%PROJECT_ROOT%\python_service"

REM 创建虚拟环境
if not exist ".venv" (
    echo   创建虚拟环境...
    python -m venv .venv
)

REM 激活虚拟环境并安装依赖
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
pip install pyinstaller -q

REM 执行打包
echo   执行 PyInstaller 打包...
python -m PyInstaller PhantomHandBackend.spec --noconfirm

if exist "dist\PhantomHandBackend.exe" (
    echo   后端打包成功
) else (
    echo   错误: 后端打包失败
    pause
    exit /b 1
)

REM 复制到 Tauri sidecar 目录
set SIDECAR_DIR=%PROJECT_ROOT%\tauri_app\src-tauri\binaries
if not exist "%SIDECAR_DIR%" mkdir "%SIDECAR_DIR%"
copy /Y "dist\PhantomHandBackend.exe" "%SIDECAR_DIR%\PhantomHandBackend-x86_64-pc-windows-msvc.exe"
echo   已复制到 Tauri sidecar 目录
echo.

REM ========== 步骤 3: 安装前端依赖 ==========
echo [3/5] 安装前端依赖...

cd "%PROJECT_ROOT%\tauri_app"

if not exist "node_modules" (
    call npm install
) else (
    echo   node_modules 已存在，跳过
)
echo.

REM ========== 步骤 4: 构建前端 ==========
echo [4/5] 构建前端...

call npm run build

if exist "dist" (
    echo   前端构建成功
) else (
    echo   错误: 前端构建失败
    pause
    exit /b 1
)
echo.

REM ========== 步骤 5: Tauri 打包 ==========
echo [5/5] Tauri 打包...

call npm run tauri build

echo.
echo ========================================
echo   打包完成!
echo ========================================
echo.
echo 安装包位于: tauri_app\src-tauri\target\release\bundle\
echo.

pause
