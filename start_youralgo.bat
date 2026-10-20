@echo off
title YourAlgo v2 -- Indian Equity & Index Options Trading Platform
cls
echo ===================================================================
echo    YourAlgo v2 -- Indian Index Options & Algorithmic Platform
echo    NSE / Upstox Official API v2
echo ===================================================================
echo.

if exist "%~dp0YourAlgo-v2\run.py" (
    cd /d "%~dp0YourAlgo-v2"
) else (
    cd /d "%~dp0"
)

python run.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Launcher encountered an issue. Press any key to exit.
    pause >nul
)
