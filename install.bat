@echo off
::============================================
:: OpenWrt CLI 一键安装脚本 (Windows 版)
:: 用法: 双击运行，或 cmd /c install.bat
::============================================

setlocal enabledelayedexpansion

set "REPO=ikuaidev/openwrt-cli"
set "INSTALL_DIR=%USERPROFILE%\.openwrt-cli"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   OpenWrt CLI 一键安装 (AI-Agent Ready)  ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ---- 检查 Python ----
echo [INFO] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 未找到 Python，请先安装 Python 3.8+
        echo   下载地址: https://www.python.org/downloads/
        echo   或者: winget install Python.Python.3.12
        pause
        exit /b 1
    )
    set "PYTHON=py"
) else (
    set "PYTHON=python"
)

echo [INFO] 使用: !PYTHON!

:: ---- 安装依赖 ----
echo.
echo [INFO] 安装 Python 依赖: paramiko, pyyaml...
!PYTHON! -m pip install paramiko pyyaml -q
if errorlevel 1 (
    echo [ERROR] pip 安装失败，尝试升级 pip...
    !PYTHON! -m pip install --upgrade pip -q
    !PYTHON! -m pip install paramiko pyyaml -q
)
echo [DONE] 依赖就绪

:: ---- 下载/更新 CLI ----
echo.
if exist "%INSTALL_DIR%\.git" (
    echo [INFO] 更新 openwrt-cli...
    cd /d "%INSTALL_DIR%"
    git pull -q
) else (
    echo [INFO] 下载 openwrt-cli...
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    powershell -NoProfile -Command "
        $repo = 'ikuaidev/openwrt-cli'
        $tag = (Invoke-WebRequest -Uri 'https://api.github.com/repos/$repo/releases/latest' -UseBasicParsing | ConvertFrom-Json).tag_name
        if (-not $tag) { $tag = 'v1.0.0' }
        $url = \"https://github.com/$repo/archive/refs/tags/$tag.zip\"
        Write-Host \"[INFO] 下载 $url\"
        Invoke-WebRequest -Uri $url -OutFile \"$env:TEMP\openwrt-cli.zip\" -UseBasicParsing
        Expand-Archive -Path \"$env:TEMP\openwrt-cli.zip\" -DestinationPath '%INSTALL_DIR%' -Force
        $subdir = (Get-ChildItem '%INSTALL_DIR%' -Directory | Where-Object { $_.Name -like 'openwrt-cli-*' })[0]
        if ($subdir) {
            Copy-Item \"$subdir\*\" '%INSTALL_DIR%\' -Force
            Remove-Item $subdir.FullName -Recurse -Force
        }
        Remove-Item \"$env:TEMP\openwrt-cli.zip\" -Force
    "
)
echo [DONE] CLI 就绪

:: ---- pip install ----
echo.
echo [INFO] 安装 CLI 主命令...
cd /d "%INSTALL_DIR%"
!PYTHON! -m pip install . -q
if errorlevel 1 (
    echo [WARN] pip install 失败，openwrt 命令可能不可用
    echo [INFO] 可以直接运行: python "%INSTALL_DIR%\main.py"
)

:: ---- 写入 PATH（用户级） ----
echo.
echo [INFO] 添加到用户 PATH...
setx PATH "%PATH%;%INSTALL_DIR%" >nul 2>&1
echo [DONE] 已添加到用户 PATH

:: ---- 快速测试 ----
echo.
echo ─────────────────────────────
echo 安装完成！使用示例：
echo.
echo   openwrt -H 192.168.1.1 -u root --password your_pass --save-config
echo   openwrt monitor system
echo   openwrt -f json network interfaces
echo.

set /p TRY_TEST="是否运行快速连接测试？[y/N]: "
if /i "!TRY_TEST!"=="y" (
    echo.
    set /p TEST_IP="请输入 OpenWrt 设备 IP [默认: 192.168.1.1]: "
    if "!TEST_IP!"=="" set TEST_IP=192.168.1.1
    set /p TEST_USER="用户名 [默认: root]: "
    if "!TEST_USER!"=="" set TEST_USER=root
    set /p TEST_PASS="密码: "
    echo.
    echo [TEST] !PYTHON! "%INSTALL_DIR%\main.py" -H !TEST_IP! -u !TEST_USER! --password !TEST_PASS! monitor system
    !PYTHON! "%INSTALL_DIR%\main.py" -H !TEST_IP! -u !TEST_USER! --password !TEST_PASS! monitor system
)
echo.
pause