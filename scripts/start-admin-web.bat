@echo off
chcp 936 >nul
title AI Talent - 启动管理端 (5173)
cd /d "%~dp0..\admin_web"

rem 检查端口是否已被占用
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [提示] 端口 5173 已被占用,管理端可能已在运行。
    echo        如需重启,请先双击 scripts\stop-admin-web.bat 再启动。
    echo.
    pause
    exit /b 1
)

if not exist node_modules (
    echo [首次运行] 正在安装依赖 npm install, 国内镜像源, 请耐心等待...
    echo.
    call npm install --no-audit --no-fund --registry=https://registry.npmmirror.com
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败,请检查网络后重试。
        pause
        exit /b 1
    )
)

echo 正在启动管理端 dev server (Vite)...
start "AI Talent 管理端 5173" cmd /k "npm run dev"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo.
echo ============================================
echo  管理端已启动: http://127.0.0.1:5173
echo  账号: admin / admin123
echo  关闭方式: 双击 scripts\stop-admin-web.bat
echo ============================================
echo.
pause
