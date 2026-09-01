@echo off
chcp 936 >nul
title AI Talent - 启动小程序 H5 (5174)
cd /d "%~dp0..\miniapp"

rem 检查端口是否已被占用
netstat -ano | findstr ":5174" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [提示] 端口 5174 已被占用,小程序端可能已在运行。
    echo        如需重启,请先双击 scripts\stop-miniapp.bat 再启动。
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

echo 正在启动小程序 H5 dev server (uni-app)...
start "AI Talent 小程序 5174" cmd /k "npm run dev:h5 -- --port 5174"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5174/#/pages/index/index"
echo.
echo ============================================
echo  小程序 H5 已启动: http://127.0.0.1:5174
echo  首页地址: #/pages/index/index
echo  关闭方式: 双击 scripts\stop-miniapp.bat
echo ============================================
echo.
pause
