@echo off
title OpenWrt Router Toolkit
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while running the toolkit.
    pause
)
