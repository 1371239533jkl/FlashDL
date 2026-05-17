@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   极简视频下载器 - 打包工具
echo ========================================
echo.

echo [1/3] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller
)

echo [2/3] 开始打包...
pyinstaller video_downloader.spec --noconfirm

echo.
if exist "dist\极简视频下载器.exe" (
    echo ========================================
    echo   打包成功!
    echo   程序位置: dist\极简视频下载器.exe
    echo ========================================
    echo.
    echo 按任意键打开输出目录...
    pause >nul
    explorer "dist"
) else (
    echo [错误] 打包失败，请检查错误信息
)

pause
