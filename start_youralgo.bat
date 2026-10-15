@echo off
title YourAlgo v2 — Indian Equity Algorithmic Platform
cls
echo ===================================================================
echo    YourAlgo v2 -- Real Indian Equity Algorithmic Trading Platform
echo    NSE / Upstox Official API v2
echo ===================================================================
echo.
cd /d "%~dp0YourAlgo-v2"

python run.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Launcher encountered an issue. Press any key to exit.
    pause >nul
)
