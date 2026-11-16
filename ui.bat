@echo off
rem The browser interface: montage, voice-over and the finished videos on one page.
rem Double-click it; the browser opens at http://localhost:8765. Close this window to stop it.
title CHRH Video
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python pipeline\server.py
if errorlevel 1 pause
