@echo off
rem The console for the whole pipeline: today's videos and every step as a menu item.
rem Double-click it, or pass a script file:  chrh.bat scripts\topics_1103.txt
rem
rem Lives in the project folder, next to pipeline\.
title CHRH Video
rem UTF-8, so the banner draws as blocks instead of rubbish; the menu falls back to a plain one if this fails.
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
mode con: cols=96 lines=44 >nul 2>&1
cd /d "%~dp0"
python pipeline\menu.py %*
if errorlevel 1 pause
