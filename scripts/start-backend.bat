@echo off
chcp 936 >nul
title AI Talent - 启动后端 (8000)
cd /d "%~dp0.."

rem 1) 检查端口是否已被占用
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [提示] 端口 8000 已被占用,后端可能已在运行。
    echo        如需重启,请先双击 scripts\stop-backend.bat 再启动。
    echo.
    pause
    exit /b 1
)

rem 2) 确定 python（优先 miniconda3 base,否则用系统 python）
set "PY=python"
if exist "C:\miniconda3\python.exe" set "PY=C:\miniconda3\python.exe"
if exist "C:\Users\Administrator\miniconda3\python.exe" set "PY=C:\Users\Administrator\miniconda3\python.exe"

rem 3) 检查后端依赖,缺失则自动安装（清华镜像）
"%PY%" -c "import fastapi,uvicorn,sqlalchemy,pymysql,alembic" >nul 2>&1
if errorlevel 1 (
    echo [首次运行] 正在安装后端依赖 pip install -r requirements.txt ...
    echo.
    "%PY%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败,请检查网络后重试。
        pause
        exit /b 1
    )
)

rem 4) 检查 .env 配置
if not exist .env (
    echo [提示] 未发现 .env 配置文件!
    echo        请先复制 .env.example 为 .env 并填写数据库连接后重试。
    pause
    exit /b 1
)

rem 5) 启动后端（新窗口,热重载）
echo 正在启动后端 dev server (uvicorn app.main:app --reload)...
start "AI Talent 后端 8000" cmd /k ""%PY%" -m uvicorn app.main:app --reload"
timeout /t 6 /nobreak >nul
echo.
echo ============================================
echo  后端已启动: http://127.0.0.1:8000/docs
echo  健康检查:   http://127.0.0.1:8000/health
echo  默认账号:   admin / admin123
echo  关闭方式:   双击 scripts\stop-backend.bat
echo ============================================
echo.
pause
