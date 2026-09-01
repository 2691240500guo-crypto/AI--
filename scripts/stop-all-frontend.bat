@echo off
setlocal EnableDelayedExpansion
chcp 936 >nul
title AI Talent - 关闭前端全部 (5173 + 5174)

for %%P in (5173 5174) do (
    echo.
    echo ===== 检查端口 %%P =====
    set "FOUND=0"
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
        set "FOUND=1"
        taskkill /F /PID %%p >nul 2>&1 && echo   已结束进程 PID=%%p || echo   进程 PID=%%p 结束失败
    )
    if "!FOUND!"=="0" echo   端口 %%P 无监听进程,未启动。
)
echo.
echo 前端服务检查完毕,可双击 start-*.bat 重新启动。
echo.
pause
