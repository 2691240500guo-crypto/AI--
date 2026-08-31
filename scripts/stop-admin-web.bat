@echo off
setlocal EnableDelayedExpansion
chcp 936 >nul
title AI Talent - 关闭管理端 (5173)
set "PORT=5173"
set "FOUND=0"

echo 正在查找端口 %PORT% 上监听的进程...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    set "FOUND=1"
    taskkill /F /PID %%p >nul 2>&1 && echo   已结束进程 PID=%%p || echo   进程 PID=%%p 结束失败
)
if "!FOUND!"=="0" (
    echo 端口 %PORT% 无监听进程,管理端可能未启动。
) else (
    echo.
    echo 管理端 [5173] 已关闭。
)
echo.
pause
